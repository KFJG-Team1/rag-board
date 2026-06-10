from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pr_atlas_mvp.parsing.models import (
    DiffHunk,
    ImportBatch,
    PullRequestFile as ParsedPullRequestFile,
)
from pr_atlas_mvp.postgres.schema import (
    FilePath,
    PullRequest,
    PullRequestFile as StoredPullRequestFile,
    PullRequestHunk,
    RawPayload,
    Repository,
)


def upsert_repository(
    session: Session,
    repo_key: str,
    owner: str,
    name: str,
) -> Repository:
    repository = session.scalar(
        select(Repository).where(Repository.repo_key == repo_key)
    )
    if repository is None:
        repository = Repository(repo_key=repo_key, owner=owner, name=name)
        session.add(repository)
    else:
        repository.owner = owner
        repository.name = name
        repository.updated_at = now_utc()

    session.flush()
    return repository


def upsert_pull_request(
    session: Session,
    pr_key: str,
    repository: Repository,
    repo_key: str,
    batch: ImportBatch,
) -> PullRequest:
    pr = batch.pull_request
    pull_request = session.scalar(
        select(PullRequest).where(PullRequest.pr_key == pr_key)
    )

    values = {
        "repository_id": repository.id,
        "repo_key": repo_key,
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "state": pr.state,
        "base_ref": pr.base_ref,
        "head_ref": pr.head_ref,
        "base_sha": pr.base_sha,
        "head_sha": pr.head_sha,
        "updated_at": parse_github_timestamp(pr.updated_at),
        "labels": list(pr.labels),
        "raw_graphql": pr.raw_graphql,
        "stored_at": now_utc(),
    }

    if pull_request is None:
        pull_request = PullRequest(pr_key=pr_key, **values)
        session.add(pull_request)
    else:
        for field, value in values.items():
            setattr(pull_request, field, value)

    session.flush()
    return pull_request


def upsert_file_path(
    session: Session,
    repository: Repository,
    path: str,
    path_tree: str,
) -> FilePath:
    file_path = session.scalar(
        select(FilePath).where(
            FilePath.repository_id == repository.id,
            FilePath.path == path,
        )
    )
    if file_path is None:
        file_path = FilePath(
            repository_id=repository.id,
            path=path,
            path_tree=path_tree,
        )
        session.add(file_path)
    else:
        file_path.path_tree = path_tree
        file_path.updated_at = now_utc()

    session.flush()
    return file_path


def insert_pr_file(
    session: Session,
    pull_request: PullRequest,
    file_path: FilePath,
    pr_file_key: str,
    file: ParsedPullRequestFile,
) -> StoredPullRequestFile:
    pr_file = StoredPullRequestFile(
        pr_file_key=pr_file_key,
        pull_request_id=pull_request.id,
        file_path_id=file_path.id,
        path=file.path,
        path_tree=file.path_tree,
        status=file.status,
        additions=file.additions,
        deletions=file.deletions,
        changes=file.changes,
        patch=file.patch,
        raw_rest=file.raw_rest,
    )
    session.add(pr_file)
    session.flush()
    return pr_file


def insert_pr_file_hunk(
    session: Session,
    pr_file: StoredPullRequestFile,
    pr_file_key: str,
    hunk_index: int,
    hunk: DiffHunk,
) -> None:
    hunk_key = f"{pr_file_key}:hunk-{hunk_index}"
    session.add(
        PullRequestHunk(
            hunk_key=hunk_key,
            pr_file_id=pr_file.id,
            hunk_index=hunk_index,
            old_start=hunk.old_start,
            old_lines=hunk.old_lines,
            new_start=hunk.new_start,
            new_lines=hunk.new_lines,
            header=hunk.header,
            line_count=len(hunk.lines),
            hunk_json=asdict(hunk),
        )
    )


def upsert_raw_payload(
    session: Session,
    entity_type: str,
    entity_key: str,
    source: str,
    payload: dict[str, Any],
) -> None:
    raw_payload = session.scalar(
        select(RawPayload).where(
            RawPayload.entity_type == entity_type,
            RawPayload.entity_key == entity_key,
            RawPayload.source == source,
        )
    )
    if raw_payload is None:
        session.add(
            RawPayload(
                entity_type=entity_type,
                entity_key=entity_key,
                source=source,
                payload=payload,
            )
        )
    else:
        raw_payload.payload = payload
        raw_payload.captured_at = now_utc()


def delete_pr_file_snapshot(
    session: Session,
    pull_request: PullRequest,
    pr_key: str,
) -> None:
    session.execute(
        delete(StoredPullRequestFile).where(
            StoredPullRequestFile.pull_request_id == pull_request.id
        )
    )
    session.execute(
        delete(RawPayload).where(
            RawPayload.entity_type == "pr_file",
            RawPayload.entity_key.like(f"{pr_key}:%"),
            RawPayload.source == "github_rest",
        )
    )


def parse_github_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def now_utc() -> datetime:
    return datetime.now(UTC)
