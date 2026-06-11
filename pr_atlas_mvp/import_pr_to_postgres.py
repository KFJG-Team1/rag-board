#!/usr/bin/env python3
"""GitHub PR을 가져와 PostgreSQL에 저장한다."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pr_atlas_mvp.parsing.github_client import fetch_pr_numbers_rest
from pr_atlas_mvp.parsing.runner import fetch_import_batch
from pr_atlas_mvp.postgres.connection import connect_database
from pr_atlas_mvp.postgres.store import store_import_batch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GitHub PR을 가져와 PostgreSQL에 저장합니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료")
    parser.add_argument("--owner", required=True, help="저장소 owner, 예: python")
    parser.add_argument("--repo", required=True, help="저장소 이름, 예: cpython")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pr", type=int, help="Pull Request 번호")
    mode.add_argument(
        "--batch",
        action="store_true",
        help="PR 목록을 페이지 단위로 가져와 여러 PR을 저장합니다.",
    )
    parser.add_argument(
        "--state",
        choices=("open", "closed", "all"),
        default="all",
        help="--batch에서 가져올 PR 상태. 기본값: all",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="--batch에서 가져올 GitHub PR 목록 페이지. 기본값: 1",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="--batch에서 한 번에 가져올 PR 개수. GitHub API 최대값은 100입니다.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="PostgreSQL 접속 URL. 없으면 .env의 DATABASE_URL을 사용합니다.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="테이블/인덱스 생성 단계를 건너뛰고 저장만 실행합니다.",
    )
    args = parser.parse_args()
    validate_args(parser, args)
    return args


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.page < 1:
        parser.error("--page는 1 이상이어야 합니다.")
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit은 1 이상 100 이하여야 합니다.")


def load_local_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "GITHUB_TOKEN이 필요합니다.\n"
            "프로젝트 루트의 .env 파일에 아래처럼 넣어주세요.\n"
            "  GITHUB_TOKEN=github_pat_xxx"
        )
    return token


def get_database_url(args: argparse.Namespace) -> str:
    database_url = args.database_url.strip()
    if not database_url:
        raise SystemExit(
            "DATABASE_URL이 필요합니다.\n"
            "프로젝트 루트의 .env 파일에 아래처럼 넣어주세요.\n"
            "  DATABASE_URL=postgresql://user:password@localhost:5432/pr_atlas"
        )
    return database_url


def main() -> None:
    load_local_env()
    args = parse_args()
    token = get_github_token()
    database_url = get_database_url(args)

    if args.pr is not None:
        pr_numbers = [args.pr]
    else:
        print(
            "GitHub         : "
            f"{args.owner}/{args.repo} PR 목록 가져오는 중 "
            f"(state={args.state}, page={args.page}, limit={args.limit})"
        )
        pr_numbers = fetch_pr_numbers_rest(
            args.owner,
            args.repo,
            token,
            state=args.state,
            page=args.page,
            per_page=args.limit,
        )
        if not pr_numbers:
            print("가져올 PR이 없습니다.")
            return

    print(f"대상 PR        : {len(pr_numbers)}개")
    with connect_database(database_url) as session:
        for index, pr_number in enumerate(pr_numbers, start=1):
            print(
                "GitHub         : "
                f"[{index}/{len(pr_numbers)}] "
                f"{args.owner}/{args.repo}#{pr_number} 가져오고 파싱하는 중"
            )
            batch = fetch_import_batch(args.owner, args.repo, pr_number, token)

            print("PostgreSQL     : 연결 및 저장 중")
            result = store_import_batch(
                session,
                batch,
                create_schema=not args.skip_schema and index == 1,
            )

            print(
                "저장 완료      : "
                f"{result.pr_key}, files={result.file_count}, hunks={result.hunk_count}"
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\n중단되었습니다.")
