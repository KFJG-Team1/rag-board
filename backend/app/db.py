import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://localhost:5432/corporate_memory",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


# DATABASE_URL = 창고 주소
# engine = 창고로 가는 연결 통로/관리자
# Session = 창고 안에서 물건을 넣고 빼는 작업자

# | **개념** | **이 프로젝트에서 어디에 해당?** | **언제 다룸** |
# | --- | --- | --- |
# | DB 세션 | SessionLocal, get_db() | 002 |
# | 데이터 모델 | Company, EarningsCall, Transcript, Chunk, Claim | 003 |
# | ORM | SQLAlchemy model ↔ PostgreSQL table 연결 | 003부터 |
# | Join | 회사별 claim 조회, call별 chunk 조회 | 005 이후 |
# | PK | 각 테이블의 id | 003 |
# | FK | company_id, call_id, transcript_id, chunk_id | 003 |
# | 정규화 | 회사/콜/원문/chunk/claim을 테이블로 나눔 | 003 |
# | ERD 1:N | 회사 1개 → 어닝콜 여러 개, 원문 1개 → chunk 여러 개 | 003 |
# | ERD N:M | 지금 MVP에는 거의 없음 | 나중 |
# | 트랜잭션 | transcript/chunks/claims 저장을 한 번에 commit/rollback | 005 이후 |
