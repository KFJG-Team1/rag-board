# 001 현재상황 보고 및 002 DB 세팅 계획

## 1. 요약

001 RESET은 Corporate Memory 백엔드 프로젝트를 처음부터 다시 시작할 수 있도록 base skeleton을 정리한 작업이다.

현재 상태는 완성된 MVP가 아니라, FastAPI 기본 앱과 `/health` 확인, 그리고 이후 단계에서 채울 파일 자리만 준비된 상태다.

다음 단계는 `002: DB 연결 skeleton 채우기`다. 002에서는 PostgreSQL에 연결하기 위한 최소 DB 설정을 `backend/app/db.py`에 추가한다.

## 2. 001에서 정리된 현재 상태

- 프로젝트 이름 / 앱 title: `Corporate Memory Skeleton`
- FastAPI 기본 앱 존재
- `GET /health` 존재
- 기본 포트: `8000`
- `8001`은 `8000`이 이미 사용 중일 때만 쓰는 임시 대안
- Python 기준: `backend/.venv`의 Python `3.12.13`
- `README.md`와 `BUILD_STEPS.md`는 skeleton 기준으로 정리됨
- `backend/app/db.py`는 아직 DB 연결 전 placeholder
- `backend/app/models.py`는 003에서 SQLAlchemy ORM 모델 정의 완료
- `backend/app/routers/ingest.py`는 0 count skeleton 응답
- `backend/app/services/chunker.py`는 `return []` skeleton
- `backend/app/services/claim_extractor.py`는 `return []` skeleton

## 3. 현재 파일 구조

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── ingest.py
│   └── services/
│       ├── __init__.py
│       ├── chunker.py
│       └── claim_extractor.py
├── data/
│   └── nvidia_transcript.txt
└── requirements.txt
```

루트 문서:

```text
README.md
BUILD_STEPS.md
docs/reports/001_STATUS_AND_002_DB_PLAN.md
```

## 4. 확인된 실행 기준

기본 실행 위치는 `backend` 폴더다.

```bash
cd backend
source .venv/bin/activate
python --version
python -m uvicorn app.main:app --reload --port 8000
```

헬스체크:

```bash
curl http://localhost:8000/health
```

기대 결과:

```json
{"status":"ok"}
```

문서 확인:

```text
http://localhost:8000/docs
```

기대 title:

```text
Corporate Memory Skeleton
```

## 5. 주의할 점

- 현재 실행 기준은 `backend/.venv`로 고정한다.
- 루트 `.venv`가 있더라도 이 프로젝트 실행 기준으로 사용하지 않는다.
- 가상환경 관련 삭제나 재생성은 사용자 지시 없이 진행하지 않는다.
- 명령은 `cd backend` 후 `source .venv/bin/activate`를 전제로 한다.
- 002 작업 기준 Python은 `backend/.venv/bin/python --version`으로 확인한다.
- 현재는 DB 저장, chunking, claim extraction이 구현되지 않은 상태다.
- `backend/app/__pycache__` 같은 캐시는 실행 중 다시 생길 수 있으며 기능 코드가 아니다.

## 6. 002 DB 세팅 목표

002의 목표는 PostgreSQL 연결 skeleton을 실제 연결 코드로 채우는 것이다.

단, 002에서는 아직 테이블 생성과 ingest 저장 로직을 구현하지 않는다.

002에서 할 일:

- `backend/app/db.py`에 `DATABASE_URL` 설정 추가
- `python-dotenv` 기반 `.env` 로드 추가
- SQLAlchemy `engine` 생성
- SQLAlchemy `SessionLocal` 생성
- SQLAlchemy `Base` 선언
- FastAPI dependency로 사용할 `get_db()` 함수 추가
- `.env.example` 생성 여부 검토
- `README.md` 또는 `BUILD_STEPS.md`에 `DATABASE_URL` 설정 방법 보강

## 7. 002에서 만질 파일

주요 대상:

```text
backend/app/db.py
```

확인 또는 보강 대상:

```text
backend/requirements.txt
README.md
BUILD_STEPS.md
.env.example
```

## 8. 002에서 하지 않을 것

- `models.py`에 5개 테이블을 정의하지 않는다. 이것은 003에서 한다.
- `create_tables()` startup 연결을 하지 않는다. 이것은 003 이후에 판단한다.
- `POST /ingest/transcript` 저장 로직을 만들지 않는다. 이것은 005에서 한다.
- MCP, RAG, LangGraph, pgvector, OpenAI API, 프론트엔드, 관리자 화면, Trust Score를 하지 않는다.

## 9. 002 완료 기준

- `DATABASE_URL`을 환경변수 또는 `.env`에서 읽을 수 있다.
- SQLAlchemy `engine`이 정의된다.
- SQLAlchemy `SessionLocal`이 정의된다.
- SQLAlchemy `Base`가 정의된다.
- `get_db()`를 import할 수 있다.
- 앱 실행 시 DB 작업을 강제로 수행하지 않는다.
- DB가 꺼져 있어도 `/health`는 깨지지 않아야 한다.

## 10. 002 작업 요청서 초안

```text
작업 002: DB 연결 skeleton 채우기.

backend/app/db.py에 dotenv 기반 DATABASE_URL 로딩, SQLAlchemy engine, SessionLocal, Base, get_db()를 추가한다.

아직 models 정의, create_tables, ingest 저장 로직은 구현하지 않는다.

/health가 DB 없이도 유지되는지 확인한다.
```

## 11. 관리자 판단

002는 진행해도 된다.

다만 002를 시작하기 전에 아래 두 가지를 확인하면 좋다.

- PostgreSQL을 로컬에서 직접 실행할지, Docker로 실행할지 결정
- 실제 DB 이름을 `corporate_memory`, `ragmcp`, 또는 다른 이름 중 하나로 고정

현재 프로젝트 명을 기준으로는 `corporate_memory`가 가장 자연스럽다.

## 12. 003 진행 메모

003에서 `backend/app/models.py`에 아래 SQLAlchemy ORM 모델을 정의한다.

- `Company` → `companies`
- `EarningsCall` → `earnings_calls`
- `Transcript` → `transcripts`
- `Chunk` → `chunks`
- `Claim` → `claims`

FK 연결:

```text
earnings_calls.company_id -> companies.id
transcripts.call_id -> earnings_calls.id
chunks.transcript_id -> transcripts.id
claims.chunk_id -> chunks.id
claims.company_id -> companies.id
```

아직 하지 않는 것:

```text
Base.metadata.create_all()
create_tables()
main.py startup 연결
POST /ingest/transcript 저장 로직
chunking 저장
claim 저장
```

## 13. 004 진행 메모

004에서 `backend/app/schemas.py`의 Pydantic 요청/응답 데이터 계약을 점검한다.

요청 모델:

```text
TranscriptIngestRequest
- ticker
- company_name
- industry
- quarter
- event_date
- source_url
- raw_text
- language
```

응답 모델:

```text
TranscriptIngestResponse
- company_id
- call_id
- transcript_id
- chunk_count
- claim_count
```

확인 내용:

```text
event_date는 date | None으로 유지한다.
language 기본값은 "en"으로 유지한다.
저장 로직, DB 연결, chunking, claim extraction은 아직 구현하지 않는다.
```

## 14. 005 진행 메모

005에서 `POST /ingest/transcript`에 metadata 저장 흐름을 추가한다.

저장 대상:

```text
companies
earnings_calls
transcripts
```

이번 단계에서 유지하는 범위:

```text
chunk_count = 0
claim_count = 0
chunker 연결 안 함
claim_extractor 연결 안 함
chunks 저장 안 함
claims 저장 안 함
```

학습용 MVP 기준으로 `create_tables()`를 추가하고, FastAPI startup에서 호출한다.
Alembic은 아직 도입하지 않는다.
