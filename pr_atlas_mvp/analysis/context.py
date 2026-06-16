from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from pr_atlas_mvp.analysis.models import (
    FileChangeInfo,
    HunkInfo,
    PullRequestInfo,
    RagDocument,
    SourceContext,
)
from pr_atlas_mvp.postgres.schema import (
    PullRequest,
    PullRequestFile,
    PullRequestHunk,
    Repository,
)


def load_source_context(
    session: Session,
    *,
    owner: str,
    repo: str,
    pr_numbers: tuple[int, ...],
) -> SourceContext:
    repository = session.scalar(
        select(Repository).where(Repository.owner == owner, Repository.name == repo)
    )
    if repository is None:
        raise ValueError(f"Repository is not imported: {owner}/{repo}")

    pull_requests = list(
        session.scalars(
            select(PullRequest)
            .where(
                PullRequest.repository_id == repository.id,
                PullRequest.number.in_(pr_numbers),
            )
            .order_by(PullRequest.number)
        )
    )
    found_numbers = {pr.number for pr in pull_requests}
    missing = [number for number in pr_numbers if number not in found_numbers]
    if missing:
        raise ValueError(f"Pull requests are not imported for {owner}/{repo}: {missing}")

    pr_infos = tuple(
        PullRequestInfo(
            id=pr.id,
            number=pr.number,
            title=pr.title,
            url=pr.url,
            state=pr.state,
            base_ref=pr.base_ref,
            head_ref=pr.head_ref,
            base_sha=pr.base_sha,
            head_sha=pr.head_sha,
            labels=tuple(pr.labels),
        )
        for pr in pull_requests
    )
    pr_id_to_number = {pr.id: pr.number for pr in pull_requests}
    pr_ids = tuple(pr_id_to_number)

    file_rows = list(
        session.scalars(
            select(PullRequestFile)
            .where(PullRequestFile.pull_request_id.in_(pr_ids))
            .order_by(PullRequestFile.path, PullRequestFile.pull_request_id)
        )
    )
    file_changes = tuple(
        FileChangeInfo(
            id=row.id,
            pull_request_id=row.pull_request_id,
            pr_number=pr_id_to_number[row.pull_request_id],
            file_path_id=row.file_path_id,
            path=row.path,
            status=row.status,
            additions=row.additions,
            deletions=row.deletions,
            changes=row.changes,
            patch=row.patch,
        )
        for row in file_rows
    )

    file_id_to_change = {file.id: file for file in file_changes}
    hunk_rows = list(
        session.scalars(
            select(PullRequestHunk)
            .where(PullRequestHunk.pr_file_id.in_(tuple(file_id_to_change)))
            .order_by(PullRequestHunk.pr_file_id, PullRequestHunk.hunk_index)
        )
    )
    hunks = tuple(
        HunkInfo(
            id=row.id,
            pr_file_id=row.pr_file_id,
            pull_request_id=file_id_to_change[row.pr_file_id].pull_request_id,
            pr_number=file_id_to_change[row.pr_file_id].pr_number,
            file_path_id=file_id_to_change[row.pr_file_id].file_path_id,
            path=file_id_to_change[row.pr_file_id].path,
            hunk_index=row.hunk_index,
            old_start=row.old_start,
            old_lines=row.old_lines,
            new_start=row.new_start,
            new_lines=row.new_lines,
            header=row.header,
            hunk_json=row.hunk_json,
        )
        for row in hunk_rows
    )

    return SourceContext(
        repository_id=repository.id,
        repo_key=repository.repo_key,
        owner=repository.owner,
        repo=repository.name,
        pull_requests=pr_infos,
        file_changes=file_changes,
        hunks=hunks,
    )


def build_rag_documents(context: SourceContext) -> tuple[RagDocument, ...]:
    documents: list[RagDocument] = [
        RagDocument(
            document_id=f"repository:{context.repository_id}",
            document_type="repository_summary",
            repository_id=context.repository_id,
            pull_request_id=None,
            file_path_id=None,
            path=None,
            title=f"{context.owner}/{context.repo}",
            content=(
                f"Repository {context.owner}/{context.repo} with "
                f"{len(context.pull_requests)} selected PRs and "
                f"{len(context.file_changes)} changed files."
            ),
            metadata={"repo_key": context.repo_key},
        )
    ]

    files_by_pr: dict[int, list[FileChangeInfo]] = defaultdict(list)
    for file_change in context.file_changes:
        files_by_pr[file_change.pull_request_id].append(file_change)

    for pr in context.pull_requests:
        changed_paths = [file.path for file in files_by_pr.get(pr.id, [])]
        documents.append(
            RagDocument(
                document_id=f"pull_request:{pr.id}",
                document_type="pr_summary",
                repository_id=context.repository_id,
                pull_request_id=pr.id,
                file_path_id=None,
                path=None,
                title=f"PR #{pr.number}: {pr.title}",
                content=(
                    f"PR #{pr.number} {pr.title}. "
                    f"Changed files: {', '.join(changed_paths[:20])}."
                ),
                metadata={
                    "pr_number": pr.number,
                    "state": pr.state,
                    "labels": list(pr.labels),
                },
            )
        )

    for file_change in context.file_changes:
        documents.append(
            RagDocument(
                document_id=f"pr_file_change:{file_change.id}",
                document_type="pr_file_change",
                repository_id=context.repository_id,
                pull_request_id=file_change.pull_request_id,
                file_path_id=file_change.file_path_id,
                path=file_change.path,
                title=f"PR #{file_change.pr_number} changed {file_change.path}",
                content=(
                    f"{file_change.status} {file_change.path}: "
                    f"+{file_change.additions} -{file_change.deletions} "
                    f"({file_change.changes} changed lines)."
                ),
                metadata={
                    "pr_number": file_change.pr_number,
                    "status": file_change.status,
                    "additions": file_change.additions,
                    "deletions": file_change.deletions,
                    "changes": file_change.changes,
                },
            )
        )

    for hunk in context.hunks:
        patch_excerpt = _hunk_excerpt(hunk)
        documents.append(
            RagDocument(
                document_id=f"diff_hunk:{hunk.id}",
                document_type="diff_hunk",
                repository_id=context.repository_id,
                pull_request_id=hunk.pull_request_id,
                file_path_id=hunk.file_path_id,
                path=hunk.path,
                title=f"PR #{hunk.pr_number} hunk {hunk.path}:{hunk.new_start}",
                content=patch_excerpt,
                metadata={
                    "pr_number": hunk.pr_number,
                    "new_start": hunk.new_start,
                    "new_lines": hunk.new_lines,
                    "old_start": hunk.old_start,
                    "old_lines": hunk.old_lines,
                    "header": hunk.header,
                },
            )
        )

    return tuple(documents)


def _hunk_excerpt(hunk: HunkInfo) -> str:
    lines = hunk.hunk_json.get("lines", [])
    rendered: list[str] = [hunk.header]
    for line in lines[:40]:
        line_type = line.get("type", "context")
        prefix = {"addition": "+", "deletion": "-", "context": " "}.get(line_type, " ")
        rendered.append(f"{prefix}{line.get('content', '')}")
    return "\n".join(rendered)
