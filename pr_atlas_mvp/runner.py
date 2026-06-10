from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from pr_atlas_mvp.github_client import fetch_pr_files_rest, fetch_pr_graphql
from pr_atlas_mvp.normalizer import normalize_import_batch
from pr_atlas_mvp.printer import (
    print_db_plan,
    print_example_queries,
    print_normalized_json_preview,
    print_section,
    print_summary,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GitHub GraphQL + REST로 PR 하나를 가져오고 DB 저장 계획을 출력합니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료")
    parser.add_argument("--owner", required=True, help="저장소 owner, 예: python")
    parser.add_argument("--repo", required=True, help="저장소 이름, 예: cpython")
    parser.add_argument("--pr", required=True, type=int, help="Pull Request 번호")
    parser.add_argument(
        "--json-preview-lines",
        type=int,
        default=120,
        help="정규화된 JSON 미리보기에서 출력할 최대 줄 수",
    )
    return parser.parse_args()


def load_local_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "GitHub GraphQL API는 익명 요청을 허용하지 않으므로 GITHUB_TOKEN이 필요합니다.\n"
            "프로젝트 루트의 .env 파일에 아래처럼 넣어주세요.\n"
            "  GITHUB_TOKEN=github_pat_xxx\n"
            "또는 터미널에서 직접 export해도 됩니다.\n"
            "  export GITHUB_TOKEN=github_pat_xxx\n"
            "  python3 -m pr_atlas_mvp.fetch_pr_main --owner python --repo cpython --pr 123456"
        )
    return token


def run_one_pr_import(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    json_preview_lines: int,
) -> None:
    print_section("0) GitHub에서 데이터 가져오기")
    print(f"GraphQL: {owner}/{repo}#{pr_number} PR 메타데이터 가져오는 중")
    graphql_repository = fetch_pr_graphql(owner, repo, pr_number, token)

    print(f"REST    : PR #{pr_number}의 변경 파일과 patch 가져오는 중")
    rest_files = fetch_pr_files_rest(owner, repo, pr_number, token)

    batch = normalize_import_batch(owner, repo, graphql_repository, rest_files)

    print_summary(batch)
    print_normalized_json_preview(batch, json_preview_lines)
    print_db_plan(batch)
    print_example_queries()


def main() -> int:
    load_local_env()
    args = parse_args()
    token = get_github_token()
    run_one_pr_import(
        owner=args.owner,
        repo=args.repo,
        pr_number=args.pr,
        token=token,
        json_preview_lines=args.json_preview_lines,
    )
    return 0
