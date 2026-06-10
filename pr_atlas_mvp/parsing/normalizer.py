from __future__ import annotations

import re
from typing import Any

from pr_atlas_mvp.parsing.models import ImportBatch, PullRequestFile, PullRequestSnapshot
from pr_atlas_mvp.parsing.patch_parser import parse_patch


def path_to_ltree(path: str) -> str:
    labels = []
    for raw_part in path.split("/"):
        label = re.sub(r"[^A-Za-z0-9_]+", "_", raw_part).strip("_").lower()
        if not label:
            label = "empty"
        if label[0].isdigit():
            label = f"_{label}"
        labels.append(label[:200])
    return ".".join(labels)


def normalize_import_batch(
    owner: str,
    repo: str,
    graphql_repository: dict[str, Any],
    rest_files: list[dict[str, Any]],
) -> ImportBatch:
    pr = graphql_repository["pullRequest"]
    gql_by_path = {item["path"]: item for item in pr["changedFiles"]["nodes"]}
    rest_by_path = {item["filename"]: item for item in rest_files}

    ordered_paths = collect_ordered_paths(pr["changedFiles"]["nodes"], rest_files)
    files = [
        normalize_file(path, gql_by_path.get(path, {}), rest_by_path.get(path, {}))
        for path in ordered_paths
    ]
    labels = [node["name"] for node in pr.get("labels", {}).get("nodes", [])]

    snapshot = PullRequestSnapshot(
        number=pr["number"],
        title=pr["title"],
        url=pr["url"],
        state=pr["state"],
        base_ref=pr["baseRefName"],
        head_ref=pr["headRefName"],
        base_sha=pr.get("baseRefOid"),
        head_sha=pr["headRefOid"],
        updated_at=pr["updatedAt"],
        labels=labels,
        files=files,
        raw_graphql=pr,
    )

    return ImportBatch(repository={"owner": owner, "name": repo}, pull_request=snapshot)


def collect_ordered_paths(
    graphql_files: list[dict[str, Any]],
    rest_files: list[dict[str, Any]],
) -> list[str]:
    ordered_paths: list[str] = []
    seen_paths = set()

    for graphql_file in graphql_files:
        ordered_paths.append(graphql_file["path"])
        seen_paths.add(graphql_file["path"])

    for rest_file in rest_files:
        path = rest_file["filename"]
        if path not in seen_paths:
            ordered_paths.append(path)
            seen_paths.add(path)

    return ordered_paths


def normalize_file(
    path: str,
    graphql_file: dict[str, Any],
    rest_file: dict[str, Any],
) -> PullRequestFile:
    patch = rest_file.get("patch")
    additions = int(rest_file.get("additions", graphql_file.get("additions", 0)) or 0)
    deletions = int(rest_file.get("deletions", graphql_file.get("deletions", 0)) or 0)
    changes = int(rest_file.get("changes", additions + deletions) or 0)

    return PullRequestFile(
        path=path,
        path_tree=path_to_ltree(path),
        status=rest_file.get("status") or graphql_file.get("changeType", "UNKNOWN").lower(),
        additions=additions,
        deletions=deletions,
        changes=changes,
        patch=patch,
        hunks=parse_patch(patch),
        raw_rest=rest_file,
    )
