from datetime import date

from pydantic import BaseModel, Field


# Pydantic BaseModel은 API로 들어오는 JSON을 Python 객체로 검증/변환한다.
# 이 모델은 POST /ingest/transcript 요청 body의 데이터 계약이다.
class TranscriptIngestRequest(BaseModel):
    # ticker는 NVDA 같은 회사 식별용 주식 심볼이다.
    ticker: str = Field(..., examples=["NVDA"])
    # company_name은 사람이 읽는 회사명이다.
    company_name: str = Field(..., examples=["NVIDIA"])
    # industry는 없을 수도 있으므로 None을 허용한다.
    industry: str | None = Field(default=None, examples=["Semiconductor"])
    # quarter는 "2025 Q2" 같은 어닝콜 기준 분기다.
    quarter: str = Field(..., examples=["2025 Q2"])
    # event_date는 "2025-08-27" 같은 문자열을 date 타입으로 파싱한다.
    event_date: date | None = Field(default=None, examples=["2025-08-27"])
    # source_url은 원문 출처다. 로컬 더미 데이터면 "local"을 쓸 수 있다.
    source_url: str | None = Field(default=None, examples=["local"])
    # raw_text는 아직 chunking하지 않은 transcript 원문 전체다.
    raw_text: str
    # language는 기본값을 영어(en)로 둔다.
    language: str = "en"


# 이 모델은 POST /ingest/transcript 응답 body의 데이터 계약이다.
# 지금 skeleton에서는 0을 반환하지만, 이후 저장 단계에서는 실제 id/count가 들어간다.
class TranscriptIngestResponse(BaseModel):
    # 저장된 company row id.
    company_id: int
    # 저장된 earnings_call row id.
    call_id: int
    # 저장된 transcript row id.
    transcript_id: int
    # 생성된 chunk 개수.
    chunk_count: int
    # 생성된 claim 개수.
    claim_count: int
