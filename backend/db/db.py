import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

'''
engine: 앱 전체에서 하나
SessionLocal: 앱 전체에서 하나
Base: 앱 전체에서 하나
Session: 작업할 때마다 생성하고 닫기
'''

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL is not set")

# 앱 전체 DB 연결 관리자
engine = create_engine(DATABASE_URL)

# 세션 생성기
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# 모델 클래스들의 부모
Base = declarative_base()

# 요청마다 세션 생성/반납 fastAPI에서는 필요x 자동으로 세션 관리 해줌
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()