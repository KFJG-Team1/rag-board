from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pr_atlas_mvp.analysis.artifacts import (
    remove_repository_artifacts,
    repository_artifact_status,
)
from pr_atlas_mvp.analysis.colors import color_for_pr_number
from pr_atlas_mvp.analysis.context import load_source_context
from pr_atlas_mvp.analysis.models import AnalysisRequest, AnalysisState
from pr_atlas_mvp.analysis.serializers import serialize_canvas_layout, serialize_pr_overlay
from pr_atlas_mvp.api.config import (
    get_openai_model,
    get_openai_timeout_seconds,
    is_openai_configured,
)
from pr_atlas_mvp.api.schemas import AnalysisRunRequest, RepositoryImportRequest
from pr_atlas_mvp.parsing.github_client import fetch_pr_numbers_rest, fetch_repository_rest
from pr_atlas_mvp.parsing.runner import fetch_import_batch_rest
from pr_atlas_mvp.postgres.schema import (
    ChangeComment,
    FilePath,
    PullRequest,
    PullRequestFile,
    Repository,
    User,
    ensure_schema,
)
from pr_atlas_mvp.postgres.store import store_import_batch
from pr_atlas_mvp.postgres.writes import upsert_repository


class NotImportedError(RuntimeError):
    pass


class DuplicateRepositoryError(RuntimeError):
    pass


class GitHubImportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class DuplicateUserError(RuntimeError):
    pass


class AuthError(RuntimeError):
    pass


class LLMConfigurationError(RuntimeError):
    pass


class AuthApiService:
    def __init__(self, *, session: Session) -> None:
        self.session = session

    def signup(self, *, user_id: str, password: str) -> dict[str, Any]:
        ensure_schema(self.session)
        login_id = user_id.strip()
        existing = self.session.scalar(select(User).where(User.login_id == login_id))
        if existing is not None:
            raise DuplicateUserError("User id already exists.")
        user = User(login_id=login_id, password=password)
        self.session.add(user)
        self.session.flush()
        self.session.commit()
        return _auth_payload(user)

    def login(self, *, user_id: str, password: str) -> dict[str, Any]:
        ensure_schema(self.session)
        user = self.session.scalar(select(User).where(User.login_id == user_id.strip()))
        if user is None or user.password != password:
            raise AuthError("Invalid user id or password.")
        return _auth_payload(user)

    def logout(self) -> None:
        return None

    def current_user(self, *, user_id: str, password: str) -> dict[str, Any]:
        ensure_schema(self.session)
        user = self.session.scalar(select(User).where(User.login_id == user_id.strip()))
        if user is None or user.password != password:
            raise AuthError("Invalid user id or password.")
        return _user_payload(user)


class AtlasApiService:
    def __init__(
        self,
        *,
        session: Session,
        runner: Callable[[Session, AnalysisRequest], AnalysisState],
    ) -> None:
        self.session = session
        self.runner = runner

    def list_repositories(
        self,
        *,
        limit: int,
        offset: int,
        query: str = "",
    ) -> dict[str, Any]:
        filters = _repository_filters(query)
        stmt = (
            select(Repository, func.count(PullRequest.id).label("pull_request_count"))
            .outerjoin(PullRequest, PullRequest.repository_id == Repository.id)
            .where(*filters)
            .group_by(Repository.id)
            .order_by(Repository.owner, Repository.name)
            .limit(limit)
            .offset(offset)
        )
        total = self.session.scalar(select(func.count(Repository.id)).where(*filters)) or 0
        repositories = [
            _repository_summary(repository, pull_request_count)
            for repository, pull_request_count in self.session.execute(stmt).all()
        ]
        return {
            "repositories": repositories,
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    def get_repository(self, *, owner: str, repo: str) -> dict[str, Any]:
        repository = self._get_repository(owner=owner, repo=repo)
        return {
            "repository": _repository_summary(
                repository,
                len(repository.pull_requests),
                artifact_status=repository_artifact_status(owner, repo),
            ),
            "artifact_status": repository_artifact_status(owner, repo),
        }

    def create_repository(self, request: RepositoryImportRequest) -> dict[str, Any]:
        existing = self.session.scalar(
            select(Repository).where(
                Repository.owner == request.owner,
                Repository.name == request.repo,
            )
        )
        if existing is not None:
            raise DuplicateRepositoryError(
                f"Repository already exists: {request.owner}/{request.repo}. Use refresh instead."
            )
        return self._import_repository(
            request,
            create_if_empty=True,
            message="Repository imported.",
        )

    def refresh_repository(
        self,
        *,
        owner: str,
        repo: str,
        request: RepositoryImportRequest,
    ) -> dict[str, Any]:
        self._get_repository(owner=owner, repo=repo)
        refresh_request = RepositoryImportRequest(
            owner=owner,
            repo=repo,
            state=request.state,
            page=request.page,
            limit=request.limit,
        )
        return self._import_repository(
            refresh_request,
            create_if_empty=True,
            message="Repository refreshed.",
        )

    def delete_repository(self, *, owner: str, repo: str) -> dict[str, Any]:
        repository = self._get_repository(owner=owner, repo=repo)
        repo_key = repository.repo_key
        try:
            self.session.delete(repository)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        removed_artifacts = remove_repository_artifacts(owner, repo)
        return {
            "repository": {
                "repo_key": repo_key,
                "owner": owner,
                "name": repo,
            },
            "removed_artifacts": removed_artifacts,
            "message": "Repository deleted.",
        }

    def list_pull_requests(
        self,
        *,
        owner: str,
        repo: str,
        state: str,
        limit: int,
        offset: int,
        query: str = "",
    ) -> dict[str, Any]:
        repository = self._get_repository(owner=owner, repo=repo)
        stmt = select(PullRequest).where(PullRequest.repository_id == repository.id)
        if state != "all":
            stmt = stmt.where(PullRequest.state == state)
        pr_filters = _pull_request_filters(query)
        stmt = stmt.where(*pr_filters)
        total_stmt = select(func.count(PullRequest.id)).where(
            PullRequest.repository_id == repository.id,
            *([PullRequest.state == state] if state != "all" else []),
            *pr_filters,
        )
        total = self.session.scalar(total_stmt) or 0
        stmt = (
            stmt.order_by(PullRequest.updated_at.desc(), PullRequest.number.desc())
            .limit(limit)
            .offset(offset)
        )
        pull_requests = list(self.session.scalars(stmt))
        files_by_pr = self._files_by_pull_request(
            tuple(pr.id for pr in pull_requests)
        )

        return {
            "repository": _repository_summary(repository, len(repository.pull_requests)),
            "pull_requests": [
                _pull_request_summary(pr, files_by_pr.get(pr.id, []))
                for pr in pull_requests
            ],
            "state": state,
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    def list_comments(
        self,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        file_path_id: int,
    ) -> dict[str, Any]:
        pull_request, file_path = self._get_comment_target(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            file_path_id=file_path_id,
        )
        rows = self.session.execute(
            select(ChangeComment, User.login_id)
            .join(User, User.id == ChangeComment.author_user_id)
            .where(
                ChangeComment.pull_request_id == pull_request.id,
                ChangeComment.file_path_id == file_path.id,
            )
            .order_by(ChangeComment.created_at.asc(), ChangeComment.id.asc())
        ).all()
        return {
            "comments": [
                _comment_summary(comment, author_login_id)
                for comment, author_login_id in rows
            ]
        }

    def create_comment(
        self,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        file_path_id: int,
        author_user_id: int,
        body: str,
    ) -> dict[str, Any]:
        pull_request, file_path = self._get_comment_target(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            file_path_id=file_path_id,
        )
        author = self.session.get(User, author_user_id)
        if author is None:
            raise AuthError("Invalid or expired session.")
        comment = ChangeComment(
            pull_request_id=pull_request.id,
            file_path_id=file_path.id,
            author_user_id=author.id,
            body=body.strip(),
        )
        try:
            self.session.add(comment)
            self.session.commit()
            self.session.refresh(comment)
        except Exception:
            self.session.rollback()
            raise
        return _comment_summary(comment, author.login_id)

    def load_atlas(self, *, owner: str, repo: str, pr_numbers: tuple[int, ...]) -> dict[str, Any]:
        try:
            context = load_source_context(
                self.session,
                owner=owner,
                repo=repo,
                pr_numbers=pr_numbers,
            )
        except ValueError as exc:
            _raise_not_imported_if_applicable(exc)
            raise

        return {
            "canvas_layout": serialize_canvas_layout(context, ()),
            "pr_overlay": serialize_pr_overlay(context),
        }

    def run_analysis(self, request: AnalysisRunRequest) -> dict[str, Any]:
        if request.use_llm and not is_openai_configured():
            raise LLMConfigurationError("OPENAI_API_KEY is required for LLM analysis.")

        role_map = request.project_role_map
        if role_map is None and request.repo_root is not None:
            candidate = request.repo_root / "project-role-map.yaml"
            role_map = candidate if candidate.exists() else None

        analysis_request = AnalysisRequest(
            owner=request.owner,
            repo=request.repo,
            pr_numbers=tuple(request.pr_numbers),
            repo_root=request.repo_root,
            codeql_db=request.codeql_db,
            codeql_results=request.codeql_results,
            project_role_map=role_map,
            validation_evidence=request.validation_evidence,
            query_pack_version=request.query_pack_version,
            codeql_query_profile=request.codeql_query_profile,
            use_llm=request.use_llm,
            llm_model=get_openai_model(),
            llm_timeout_seconds=get_openai_timeout_seconds(),
            create_schema=not request.skip_schema,
        )
        try:
            state = self.runner(self.session, analysis_request)
            self.session.commit()
        except ValueError as exc:
            self.session.rollback()
            _raise_not_imported_if_applicable(exc)
            raise
        except Exception:
            self.session.rollback()
            raise
        return state.outputs

    def _import_repository(
        self,
        request: RepositoryImportRequest,
        *,
        create_if_empty: bool,
        message: str,
    ) -> dict[str, Any]:
        token = os.environ.get("GITHUB_TOKEN", "").strip() or None
        try:
            repository_payload = fetch_repository_rest(request.owner, request.repo, token)
            pr_numbers = fetch_pr_numbers_rest(
                request.owner,
                request.repo,
                token,
                state=request.state,
                page=request.page,
                per_page=request.limit,
            )
            imported_count = 0
            for index, pr_number in enumerate(pr_numbers, start=1):
                batch = fetch_import_batch_rest(
                    request.owner,
                    request.repo,
                    pr_number,
                    token,
                    repository_payload=repository_payload,
                )
                store_import_batch(
                    self.session,
                    batch,
                    create_schema=index == 1,
                )
                imported_count += 1

            if imported_count == 0 and create_if_empty:
                ensure_schema(self.session)
                transaction = (
                    self.session.begin_nested()
                    if self.session.in_transaction()
                    else self.session.begin()
                )
                with transaction:
                    upsert_repository(
                        self.session,
                        f"{request.owner}/{request.repo}",
                        request.owner,
                        request.repo,
                    )

            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        except Exception as exc:
            self.session.rollback()
            raise _to_github_import_error(exc) from exc

        repository = self._get_repository(owner=request.owner, repo=request.repo)
        return {
            "repository": _repository_summary(
                repository,
                len(repository.pull_requests),
                artifact_status=repository_artifact_status(request.owner, request.repo),
            ),
            "imported_pr_count": imported_count,
            "state": request.state,
            "page": request.page,
            "limit": request.limit,
            "message": message,
        }

    def _get_repository(self, *, owner: str, repo: str) -> Repository:
        repository = self.session.scalar(
            select(Repository).where(Repository.owner == owner, Repository.name == repo)
        )
        if repository is None:
            raise NotImportedError(f"Repository is not imported: {owner}/{repo}")
        return repository

    def _files_by_pull_request(
        self,
        pull_request_ids: tuple[int, ...],
    ) -> dict[int, list[PullRequestFile]]:
        if not pull_request_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(PullRequestFile)
                .where(PullRequestFile.pull_request_id.in_(pull_request_ids))
                .order_by(PullRequestFile.path)
            )
        )
        grouped: dict[int, list[PullRequestFile]] = defaultdict(list)
        for row in rows:
            grouped[row.pull_request_id].append(row)
        return grouped

    def _get_comment_target(
        self,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        file_path_id: int,
    ) -> tuple[PullRequest, FilePath]:
        repository = self._get_repository(owner=owner, repo=repo)
        pull_request = self.session.scalar(
            select(PullRequest).where(
                PullRequest.repository_id == repository.id,
                PullRequest.number == pr_number,
            )
        )
        if pull_request is None:
            raise NotImportedError(f"Pull request is not imported: {owner}/{repo}#{pr_number}")
        file_path = self.session.get(FilePath, file_path_id)
        if file_path is None or file_path.repository_id != repository.id:
            raise NotImportedError(f"File path is not imported: {file_path_id}")
        pr_file = self.session.scalar(
            select(PullRequestFile).where(
                PullRequestFile.pull_request_id == pull_request.id,
                PullRequestFile.file_path_id == file_path_id,
            )
        )
        if pr_file is None:
            raise NotImportedError(
                f"Pull request #{pr_number} does not change file path {file_path_id}."
            )
        return pull_request, file_path


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "user_id": user.login_id,
        "created_at": user.created_at,
    }


def _auth_payload(user: User) -> dict[str, Any]:
    return {
        "user": _user_payload(user),
    }


def _repository_filters(query: str) -> list[Any]:
    value = query.strip()
    if not value:
        return []
    pattern = f"%{value}%"
    return [
        or_(
            Repository.owner.ilike(pattern),
            Repository.name.ilike(pattern),
            Repository.repo_key.ilike(pattern),
        )
    ]


def _pull_request_filters(query: str) -> list[Any]:
    value = query.strip()
    if not value:
        return []
    pattern = f"%{value}%"
    return [
        or_(
            cast(PullRequest.number, Text).ilike(pattern),
            PullRequest.title.ilike(pattern),
            PullRequest.head_ref.ilike(pattern),
            PullRequest.base_ref.ilike(pattern),
            func.array_to_string(PullRequest.labels, " ").ilike(pattern),
        )
    ]


def _repository_summary(
    repository: Repository,
    pull_request_count: int,
    *,
    artifact_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": repository.id,
        "repo_key": repository.repo_key,
        "owner": repository.owner,
        "name": repository.name,
        "pull_request_count": pull_request_count,
        "last_imported_at": _latest_imported_at(repository),
        "artifact_status": artifact_status,
        "created_at": repository.created_at,
        "updated_at": repository.updated_at,
    }


def _latest_imported_at(repository: Repository) -> Any | None:
    timestamps = [pull_request.stored_at for pull_request in repository.pull_requests]
    return max(timestamps) if timestamps else None


def _pull_request_summary(
    pull_request: PullRequest,
    files: list[PullRequestFile],
) -> dict[str, Any]:
    body_text = _pull_request_body_text(pull_request)
    return {
        "pull_request_id": pull_request.id,
        "number": pull_request.number,
        "title": pull_request.title,
        "body_text": body_text,
        "body_excerpt": _excerpt(body_text),
        "color": color_for_pr_number(pull_request.number),
        "url": pull_request.url,
        "state": pull_request.state,
        "base_ref": pull_request.base_ref,
        "head_ref": pull_request.head_ref,
        "base_sha": pull_request.base_sha,
        "head_sha": pull_request.head_sha,
        "labels": list(pull_request.labels),
        "updated_at": pull_request.updated_at,
        "stored_at": pull_request.stored_at,
        "file_count": len(files),
        "additions": sum(file.additions for file in files),
        "deletions": sum(file.deletions for file in files),
        "changes": sum(file.changes for file in files),
        "changed_files": [
            {
                "file_path_id": file.file_path_id,
                "path": file.path,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "hunk_count": len(file.hunks),
                "patch_excerpt": _patch_excerpt(file.patch),
            }
            for file in files
        ],
    }


def _pull_request_body_text(pull_request: PullRequest) -> str | None:
    raw = pull_request.raw_graphql or {}
    for key in ("bodyText", "body", "body_text"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _excerpt(value: str | None, *, limit: int = 280) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)] + "..."


def _comment_summary(comment: ChangeComment, author_login_id: str) -> dict[str, Any]:
    return {
        "id": comment.id,
        "pull_request_id": comment.pull_request_id,
        "file_path_id": comment.file_path_id,
        "author_user_id": comment.author_user_id,
        "author_login_id": author_login_id,
        "body": comment.body,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }


def _patch_excerpt(patch: str | None, *, max_lines: int = 28) -> str | None:
    if not patch:
        return None
    lines = patch.splitlines()
    if len(lines) <= max_lines:
        return patch
    return "\n".join([*lines[:max_lines], "..."])


def _raise_not_imported_if_applicable(exc: ValueError) -> None:
    message = str(exc)
    if "not imported" in message:
        raise NotImportedError(message) from exc


def _to_github_import_error(exc: Exception) -> GitHubImportError:
    if isinstance(exc, GitHubImportError):
        return exc
    message = str(exc)
    match = re_search_http_status(message)
    if match == 404:
        return GitHubImportError(
            "GitHub repository or pull request was not found.",
            status_code=404,
        )
    if match == 403:
        return GitHubImportError(
            "GitHub API rate limit or access policy blocked the request.",
            status_code=429,
        )
    return GitHubImportError(f"GitHub import failed: {message}", status_code=502)


def re_search_http_status(message: str) -> int | None:
    for token in ("404", "403", "401", "429"):
        if f"GitHub API 요청 실패: {token}" in message:
            return int(token)
    return None
