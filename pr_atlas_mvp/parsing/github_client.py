from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_REST_URL = "https://api.github.com"
USER_AGENT = "pr-collision-atlas-mvp"


def request_json(
    url: str,
    *,
    token: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API 요청 실패: {error.code} {error.reason}\n{payload}"
        ) from error


def fetch_pr_graphql(owner: str, repo: str, pr_number: int, token: str) -> dict[str, Any]:
    query = """
    query FetchOnePullRequest($owner: String!, $repo: String!, $pr: Int!) {
      repository(owner: $owner, name: $repo) {
        id
        name
        owner {
          login
        }
        pullRequest(number: $pr) {
          id
          number
          title
          bodyText
          url
          state
          mergeable
          mergeStateStatus
          createdAt
          updatedAt
          baseRefName
          headRefName
          baseRefOid
          headRefOid
          author {
            login
          }
          labels(first: 50) {
            nodes {
              name
            }
          }
          changedFiles: files(first: 100) {
            nodes {
              path
              additions
              deletions
              changeType
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {"owner": owner, "repo": repo, "pr": pr_number},
    }
    result = request_json(GITHUB_GRAPHQL_URL, token=token, method="POST", body=payload)

    if not isinstance(result, dict):
        raise RuntimeError("GraphQL 응답 구조가 예상과 다릅니다.")
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2, ensure_ascii=False))

    repository = result.get("data", {}).get("repository")
    if not repository or not repository.get("pullRequest"):
        raise RuntimeError(f"{owner}/{repo}에서 PR #{pr_number}을 찾지 못했습니다.")

    return repository


def fetch_pr_numbers_rest(
    owner: str,
    repo: str,
    token: str,
    *,
    state: str = "all",
    page: int = 1,
    per_page: int = 100,
) -> list[int]:
    params = urllib.parse.urlencode(
        {"state": state, "per_page": per_page, "page": page}
    )
    url = f"{GITHUB_REST_URL}/repos/{owner}/{repo}/pulls?{params}"
    items = request_json(url, token=token)

    if not isinstance(items, list):
        raise RuntimeError("REST PR 목록 응답 구조가 예상과 다릅니다.")

    return [int(item["number"]) for item in items]


def fetch_pr_files_rest(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page = 1

    while True:
        params = urllib.parse.urlencode({"per_page": 100, "page": page})
        url = f"{GITHUB_REST_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files?{params}"
        page_items = request_json(url, token=token)

        if not isinstance(page_items, list):
            raise RuntimeError("REST 파일 응답 구조가 예상과 다릅니다.")

        files.extend(page_items)

        if len(page_items) < 100:
            break
        page += 1

    return files
