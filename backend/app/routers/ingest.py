from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, EarningsCall, Transcript
from app.schemas import TranscriptIngestRequest, TranscriptIngestResponse


# 이 라우터는 /ingest로 시작하는 데이터 저장 API들을 묶는다.
# FMP API를 직접 호출하는 곳은 아니다.
router = APIRouter(prefix="/ingest", tags=["ingest"])


# 최종 주소는 POST /ingest/transcript 다.
# 이 API는 FMP 등에서 받아온 transcript를 우리 JSON 양식으로 바꾼 뒤 저장하는 입구다.
# FMP 호출과 응답 변환은 나중에 별도 client/service에서 담당한다.
# 현재 005 단계에서는 companies, earnings_calls, transcripts까지만 저장한다.
# chunks와 claims는 아직 만들거나 저장하지 않으므로 count는 0으로 유지한다.
@router.post("/transcript", response_model=TranscriptIngestResponse)
def ingest_transcript(
    # payload는 이미 우리 양식에 맞게 들어온 transcript 요청 데이터다.
    # 클라이언트가 보낸 JSON이 Pydantic 검증을 거쳐 이 객체로 들어온다.
    # 이 JSON은 FMP Transcript API 응답을 변환한 결과일 수 있지만,
    # 이 함수 안에서 FMP API를 직접 호출하지는 않는다.
    payload: TranscriptIngestRequest,
    # db는 이 요청을 처리하는 동안 DB 저장에 사용할 SQLAlchemy 세션이다.
    # Depends(get_db)가 세션을 만들고, 요청 처리가 끝나면 닫아 준다.
    db: Session = Depends(get_db),
) -> TranscriptIngestResponse:
    try:
        # ticker는 회사 식별용 심볼이다.
        # 같은 회사를 같은 값으로 찾기 위해 공백을 제거하고 대문자로 통일한다.
        # 예: " nvda " -> "NVDA"
        ticker = payload.ticker.upper().strip()

        # 먼저 같은 ticker의 회사가 DB에 이미 있는지 찾는다.
        # 있으면 기존 회사를 다시 사용하고, 없으면 아래에서 새로 만든다.
        company = db.scalar(select(Company).where(Company.ticker == ticker))
        if company is None:
            # 기존 회사가 없으면 companies 테이블에 넣을 새 Company 객체를 만든다.
            company = Company(
                ticker=ticker,
                name=payload.company_name.strip(),
                industry=payload.industry.strip() if payload.industry else None,
            )
            # db.add()는 이 객체를 DB에 저장할 목록에 올리는 역할이다.
            db.add(company)
            # db.flush()는 아직 commit 전이어도 INSERT를 보내서 company.id를 받을 수 있게 한다.
            db.flush()

        # EarningsCall은 "어느 회사의 어느 분기 어닝콜인가"를 저장한다.
        # company_id에는 위에서 찾거나 만든 companies.id가 들어간다.
        earnings_call = EarningsCall(
            company_id=company.id,
            quarter=payload.quarter.strip(),
            event_date=payload.event_date,
            source_url=payload.source_url.strip() if payload.source_url else None,
        )
        db.add(earnings_call)
        db.flush()

        # Transcript는 실제 transcript 원문 텍스트를 저장한다.
        # call_id에는 방금 만든 earnings_calls.id가 들어가서 원문과 어닝콜을 연결한다.
        transcript = Transcript(
            call_id=earnings_call.id,
            raw_text=payload.raw_text,
            language=payload.language.strip() or "en",
        )
        db.add(transcript)
        db.flush()

        # 응답에 바로 사용할 id들을 commit 전에 변수에 담아 둔다.
        company_id = company.id
        call_id = earnings_call.id
        transcript_id = transcript.id

        # 여기까지 준비한 저장 작업을 DB에 최종 확정한다.
        db.commit()

        # 저장된 핵심 id와 현재 단계의 count를 응답으로 돌려준다.
        # chunk와 claim은 아직 저장하지 않았으므로 둘 다 0이다.
        return TranscriptIngestResponse(
            company_id=company_id,
            call_id=call_id,
            transcript_id=transcript_id,
            chunk_count=0,
            claim_count=0,
        )
    except Exception:
        # 중간에 오류가 나면 이번 요청에서 준비하던 DB 저장을 되돌린다.
        db.rollback()
        raise
