# Corporate Memory Skeleton

이 repo는 Corporate Memory 1차 MVP를 처음부터 따라 만들기 위한 백엔드 skeleton이다.

지금 상태는 완성된 MVP가 아니다. 현재는 FastAPI 기본 앱, `/health`, 그리고 앞으로 채울 파일 자리만 준비되어 있다.

## MVP Scope

나중에 만들 1차 MVP 범위는 아래까지만이다.

```text
더미 NVIDIA Transcript 입력
        |
        v
section / speaker 기준 chunking
        |
        v
규칙 기반 claim 추출
        |
        v
companies / earnings_calls / transcripts / chunks / claims 저장
```

지금 하지 않는 것:

```text
MCP
RAG
LangGraph
pgvector
OpenAI API
프론트엔드
관리자 화면
Trust Score
```

## Current State

현재 001 RESET 상태에서는 아래만 확인한다.

```text
FastAPI 앱이 켜진다.
GET /health가 {"status":"ok"}를 반환한다.
기본 포트는 8000이다.
Python 3.12 + backend/.venv 기준으로 실행한다.
```

DB 저장, chunking, claim extraction은 아직 구현하지 않는다.

가상환경 기준:

```text
프로젝트 실행 기준은 backend/.venv 하나로 고정한다.
루트 .venv가 있더라도 이 프로젝트 실행 기준으로 사용하지 않는다.
backend/.venv는 Python 3.12.x를 사용해야 한다.
현재 확인 기준은 Python 3.12.13이다.
```

에디터 Python interpreter 기준:

```text
VS Code/Codex 에디터의 Python interpreter는 backend/.venv/bin/python을 선택한다.
화면에 .venv (3.13.13)이 보이면 잘못 선택된 interpreter다.
올바른 확인 명령은 backend/.venv/bin/python --version 이다.
기대값은 Python 3.12.x다.
```

## Backend Structure

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

## File Roles

```text
backend/app/main.py
- FastAPI 앱 시작점
- 지금은 /health만 확인

backend/app/routers/ingest.py
- 나중에 POST /ingest/transcript를 채울 자리
- 지금은 0 count skeleton 응답만 반환

backend/app/db.py
- 002에서 DB 연결 코드를 채울 자리

backend/app/models.py
- 003에서 SQLAlchemy 테이블 모델을 채울 자리

backend/app/schemas.py
- 요청/응답 Pydantic schema 최소 skeleton

backend/app/services/chunker.py
- 006에서 transcript chunking 규칙을 채울 자리

backend/app/services/claim_extractor.py
- 008에서 claim 추출 규칙을 채울 자리

backend/data/nvidia_transcript.txt
- 더미 NVIDIA transcript 원문을 둘 자리
```

## Run Locally

처음 실행은 `backend` 폴더에서 한다.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

버전 확인:

```bash
python --version
```

기대값:

```text
Python 3.12.x
```

다른 터미널에서 확인:

```bash
curl http://localhost:8000/health
```

기대 응답:

```json
{"status":"ok"}
```

API 문서:

```text
http://localhost:8000/docs
```

상단 title은 `Corporate Memory Skeleton`이어야 한다.

8000번 포트가 이미 사용 중일 때만 임시로 8001을 쓴다.

```bash
python -m uvicorn app.main:app --reload --port 8001
```

## Next Step

다음 작업은 `002: DB 연결 skeleton 채우기`다.

## 002 DB Connection

002는 PostgreSQL 연결 준비 단계다. 아직 테이블 생성이나 데이터 저장은 하지 않는다.

FastAPI는 `DATABASE_URL` 값을 읽어 PostgreSQL 접속 주소를 준비한다.

예시:

```text
DATABASE_URL=postgresql+psycopg://localhost:5432/corporate_memory
```

의미:

```text
postgresql+psycopg: SQLAlchemy가 psycopg 드라이버로 PostgreSQL에 연결
localhost:5432: 로컬 PostgreSQL 주소와 포트
corporate_memory: 사용할 데이터베이스 이름
```

이 값은 `.env.example`을 참고해서 실제 `.env` 또는 환경변수로 설정한다.
