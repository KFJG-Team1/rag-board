from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# datetime은 날짜/시간 표현용,
# sqlalchemy 타입들은 DB 컬럼 타입 정의용,
# Mapped/mapped_column은 ORM 컬럼 선언용,
# Base는 모델 클래스를 테이블 설계도로 등록하기 위한 부모 클래스다.

# 모든 created_at 컬럼에서 같은 기준의 UTC 시간을 쓰기 위한 helper다.
# 로컬 시간대가 섞이지 않게 UTC 기준으로 저장한다.
def utc_now() -> datetime:
    return datetime.now(UTC)


# Base를 상속하면 SQLAlchemy가 이 클래스를 ORM 테이블 모델로 인식한다.
# Mapped[...]는 컬럼의 Python 타입을 표현하고, mapped_column()은 실제 DB 컬럼 설정을 담는다.
# 지금은 단순 테이블 설계 단계라 relationship()은 쓰지 않고 ForeignKey만 둔다.


# companies 테이블: 기업의 기본 정보를 저장한다.
class Company(Base):
    __tablename__ = "companies"

    # 모든 테이블의 id는 각 row를 구분하는 primary key다.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ticker는 NVDA 같은 회사 식별용 주식 심볼이다.
    ticker: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # name은 사람이 읽는 회사명이다.
    name: Mapped[str] = mapped_column(String(255))
    # industry는 아직 모를 수 있으므로 nullable로 둔다.
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # created_at은 row가 처음 만들어진 시각을 UTC로 기록한다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


# earnings_calls 테이블: 한 회사의 특정 분기 어닝콜 정보를 저장한다.
class EarningsCall(Base):
    __tablename__ = "earnings_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # companies.id를 참조해서 어떤 회사의 어닝콜인지 연결한다.
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    # 예: "2025 Q2"
    quarter: Mapped[str] = mapped_column(String(50))
    # event_date는 어닝콜 날짜이며, 모를 수 있으므로 nullable이다.
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # source_url은 원문 출처다. 로컬 더미 데이터면 "local" 같은 값이 들어갈 수 있다.
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


# transcripts 테이블: 어닝콜 원문 전체를 저장한다.
class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # earnings_calls.id를 참조해서 이 원문이 어떤 어닝콜에 속하는지 연결한다.
    call_id: Mapped[int] = mapped_column(ForeignKey("earnings_calls.id"), index=True)
    # raw_text는 아직 가공하지 않은 transcript 원문이다.
    raw_text: Mapped[str] = mapped_column(Text)
    # MVP에서는 기본 언어를 영어(en)로 둔다.
    language: Mapped[str] = mapped_column(String(20), default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


# chunks 테이블: transcript 원문을 section/speaker 기준으로 나눈 조각을 저장한다.
class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # transcripts.id를 참조해서 이 chunk가 어떤 원문에서 나왔는지 연결한다.
    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("transcripts.id"),
        index=True,
    )
    # chunk_index는 원문 안에서 chunk의 순서를 나타낸다.
    chunk_index: Mapped[int] = mapped_column(Integer)
    # section은 prepared_remarks, qa 같은 구간 이름이다.
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # speaker는 Jensen Huang, Analyst 같은 발화자 이름이다.
    speaker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # chunk_text는 해당 발화자/구간의 실제 텍스트다.
    chunk_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


# claims 테이블: chunk에서 뽑아낸 핵심 주장 후보를 저장한다.
class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # chunks.id를 참조해서 이 claim이 어떤 chunk에서 나왔는지 연결한다.
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id"), index=True)
    # companies.id를 참조해서 이 claim이 어느 회사에 대한 것인지 연결한다.
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    # topic은 AI Demand, Data Center Revenue 같은 주제명이다.
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # claim_type은 guidance, risk, outlook 같은 주장 성격이다.
    claim_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # claim_text는 실제로 추출한 주장 문장이다.
    claim_text: Mapped[str] = mapped_column(Text)
    # period_target은 next quarter 같은 대상 기간이다.
    period_target: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # metric은 revenue, margin, demand 같은 지표다.
    metric: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # direction은 increase, decrease, neutral 같은 방향성이다.
    direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # confidence는 규칙 기반 추출 결과에 대한 임시 신뢰도다.
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
