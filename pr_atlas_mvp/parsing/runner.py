from __future__ import annotations

from pr_atlas_mvp.parsing.github_client import fetch_pr_files_rest, fetch_pr_graphql
from pr_atlas_mvp.parsing.models import ImportBatch
from pr_atlas_mvp.parsing.normalizer import normalize_import_batch


def fetch_import_batch(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> ImportBatch:
    graphql_repository = fetch_pr_graphql(owner, repo, pr_number, token)
    rest_files = fetch_pr_files_rest(owner, repo, pr_number, token)

    return normalize_import_batch(owner, repo, graphql_repository, rest_files)
