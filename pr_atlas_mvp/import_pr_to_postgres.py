#!/usr/bin/env python3
"""GitHub PR 하나를 가져와 PostgreSQL에 저장한다."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pr_atlas_mvp.parsing.runner import fetch_import_batch
from pr_atlas_mvp.postgres.connection import connect_database
from pr_atlas_mvp.postgres.store import store_import_batch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GitHub PR 하나를 가져와 PostgreSQL에 저장합니다.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="도움말을 출력하고 종료")
    parser.add_argument("--owner", required=True, help="저장소 owner, 예: python")
    parser.add_argument("--repo", required=True, help="저장소 이름, 예: cpython")
    parser.add_argument("--pr", required=True, type=int, help="Pull Request 번호")
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
    return parser.parse_args()


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

    print(f"GitHub         : {args.owner}/{args.repo}#{args.pr} 가져오고 파싱하는 중")
    batch = fetch_import_batch(args.owner, args.repo, args.pr, token)

    print("PostgreSQL     : 연결 및 저장 중")
    with connect_database(database_url) as session:
        result = store_import_batch(session, batch, create_schema=not args.skip_schema)

    print(
        "저장 완료: "
        f"{result.pr_key}, files={result.file_count}, hunks={result.hunk_count}"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\n중단되었습니다.")
