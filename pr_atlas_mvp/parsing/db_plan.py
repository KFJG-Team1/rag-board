from __future__ import annotations

from typing import Any

from pr_atlas_mvp.parsing.models import ImportBatch


def build_db_rows(batch: ImportBatch) -> dict[str, list[dict[str, Any]]]:
    owner = batch.repository["owner"]
    repo = batch.repository["name"]
    pr = batch.pull_request
    repository_key = batch.repository["id"]
    pr_key = f"{repository_key}#{pr.number}"

    rows: dict[str, list[dict[str, Any]]] = {
        "repositories": [
            {
                "repo_key": repository_key,
                "owner": owner,
                "name": repo,
            }
        ],
        "pull_requests": [
            {
                "pr_key": pr_key,
                "repo_key": repository_key,
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "base_ref": pr.base_ref,
                "head_ref": pr.head_ref,
                "base_sha": pr.base_sha,
                "head_sha": pr.head_sha,
                "updated_at": pr.updated_at,
                "labels": pr.labels,
                "raw_graphql": "<jsonb: 전체 GraphQL PR 객체>",
            }
        ],
        "file_paths": [],
        "pr_files": [],
        "pr_file_hunks": [],
        "raw_payloads": [
            {
                "entity_type": "pull_request",
                "entity_key": pr_key,
                "source": "github_graphql",
                "payload": "<jsonb: 전체 GraphQL PR 객체>",
            }
        ],
    }

    seen_paths = set()
    for file in pr.files:
        file_key = f"{pr_key}:{file.path}"

        if file.path not in seen_paths:
            rows["file_paths"].append(
                {
                    "path": file.path,
                    "path_tree": file.path_tree,
                }
            )
            seen_paths.add(file.path)

        rows["pr_files"].append(
            {
                "pr_file_key": file_key,
                "pr_key": pr_key,
                "path": file.path,
                "path_tree": file.path_tree,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "raw_rest": "<jsonb: REST 파일 객체>",
            }
        )
        rows["raw_payloads"].append(
            {
                "entity_type": "pr_file",
                "entity_key": file_key,
                "source": "github_rest",
                "payload": "<jsonb: 전체 REST 파일 객체>",
            }
        )

        for hunk_index, hunk in enumerate(file.hunks, start=1):
            rows["pr_file_hunks"].append(
                {
                    "hunk_key": f"{file_key}:hunk-{hunk_index}",
                    "pr_file_key": file_key,
                    "old_start": hunk.old_start,
                    "old_lines": hunk.old_lines,
                    "new_start": hunk.new_start,
                    "new_lines": hunk.new_lines,
                    "header": hunk.header,
                    "line_count": len(hunk.lines),
                    "hunk_json": "<jsonb: 파싱된 hunk와 라인 목록>",
                }
            )

    return rows
