from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str) -> Engine:
    return create_engine(normalize_database_url(database_url), future=True)


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_database_engine(database_url)
    return sessionmaker(bind=engine, expire_on_commit=False)


def connect_database(database_url: str) -> Session:
    return create_session_factory(database_url)()
