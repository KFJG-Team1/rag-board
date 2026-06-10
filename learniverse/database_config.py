"""Database configuration helpers for Learniverse."""

import os
from pathlib import Path

from dotenv import load_dotenv


class MissingDatabaseURLError(RuntimeError):
    """Raised when DATABASE_URL is not configured."""


def load_database_url(env_file: str | Path = ".env") -> str:
    """Load DATABASE_URL from .env or the process environment."""
    # DB 접속 정보도 API 키처럼 로컬 `.env`에서 읽는다.
    # 설정이 없으면 DB 연결 단계에서 애매하게 실패하기 전에, 무엇을 넣어야 하는지 명확히 알려준다.
    load_dotenv(dotenv_path=env_file)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise MissingDatabaseURLError(
            "DATABASE_URL is not set. Add DATABASE_URL=postgresql://learniverse:learniverse@localhost:6024/learniverse to .env."
        )
    return database_url
