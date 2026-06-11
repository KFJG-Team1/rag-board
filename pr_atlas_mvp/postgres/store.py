from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from pr_atlas_mvp.parsing.models import ImportBatch
from pr_atlas_mvp.postgres.schema import ensure_schema
from pr_atlas_mvp.postgres.writes import (
    delete_pr_file_snapshot,
    insert_pr_file,
    insert_pr_file_hunk,
    upsert_file_path,
    upsert_pull_request,
    upsert_raw_payload,
    upsert_repository,
)


@dataclass(frozen=True)
class StoreResult:
    repo_key: str
    pr_key: str
    file_count: int
    hunk_count: int


def store_import_batch(
    session: Session,
    batch: ImportBatch,
    *,
    create_schema: bool = True,
) -> StoreResult:
    owner = batch.repository["owner"]
    repo = batch.repository["name"]
    repository_key = batch.repository["id"]
    pr = batch.pull_request
    pr_key = f"{repository_key}#{pr.number}"

    if create_schema:
        ensure_schema(session)

    with session.begin():
        repository = upsert_repository(session, repository_key, owner, repo)
        pull_request = upsert_pull_request(
            session,
            pr_key,
            repository,
            repository_key,
            batch,
        )

        delete_pr_file_snapshot(session, pull_request, pr_key)
        upsert_raw_payload(session, "pull_request", pr_key, "github_graphql", pr.raw_graphql)

        hunk_count = 0
        for file in pr.files:
            file_path = upsert_file_path(session, repository, file.path, file.path_tree)
            pr_file_key = f"{pr_key}:{file.path}"
            pr_file = insert_pr_file(
                session,
                pull_request,
                file_path,
                pr_file_key,
                file,
            )
            upsert_raw_payload(session, "pr_file", pr_file_key, "github_rest", file.raw_rest)

            for hunk_index, hunk in enumerate(file.hunks, start=1):
                insert_pr_file_hunk(session, pr_file, pr_file_key, hunk_index, hunk)
                hunk_count += 1

    return StoreResult(
        repo_key=repository_key,
        pr_key=pr_key,
        file_count=len(pr.files),
        hunk_count=hunk_count,
    )
