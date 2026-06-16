from __future__ import annotations

from pr_atlas_mvp.parsing.github_client import (
    fetch_pr_files_rest,
    fetch_pr_graphql,
    fetch_pr_rest,
    fetch_repository_rest,
)
from pr_atlas_mvp.parsing.models import ImportBatch
from pr_atlas_mvp.parsing.normalizer import normalize_import_batch, normalize_rest_import_batch


def fetch_import_batch(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> ImportBatch:
    graphql_repository = fetch_pr_graphql(owner, repo, pr_number, token)
    rest_files = fetch_pr_files_rest(owner, repo, pr_number, token)

    return normalize_import_batch(owner, repo, graphql_repository, rest_files)


def fetch_import_batch_rest(
    owner: str,
    repo: str,
    pr_number: int,
    token: str | None = None,
    *,
    repository_payload: dict | None = None,
) -> ImportBatch:
    repository_payload = repository_payload or fetch_repository_rest(owner, repo, token)
    pull_request_payload = fetch_pr_rest(owner, repo, pr_number, token)
    rest_files = fetch_pr_files_rest(owner, repo, pr_number, token)
    return normalize_rest_import_batch(
        owner,
        repo,
        repository_payload,
        pull_request_payload,
        rest_files,
    )
