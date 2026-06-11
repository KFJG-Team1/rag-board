# Corporate Memory 백엔드 진행표

이 문서는 Corporate Memory 1차 MVP를 처음부터 직접 따라 만들기 위한 진행표다.

한 번에 전체 MVP를 만들지 않는다. 각 단계에서 목표, 만질 파일, 완료 기준만 확인하고 다음 단계로 넘어간다.

## 001. Base skeleton 확인

목표:

```text
Python 3.12 가상환경과 FastAPI /health 기본 서버를 확인한다.
```

만질 파일:

```text
backend/app/main.py
backend/requirements.txt
README.md
```

완료 기준:

```text
backend/.venv가 Python 3.12.x를 사용한다.
python -m uvicorn app.main:app --reload --port 8000 실행 기준이 명확하다.
GET http://localhost:8000/health가 {"status":"ok"}를 반환한다.
http://localhost:8000/docs title이 Corporate Memory Skeleton이다.
```

가상환경 기준:

```text
반드시 backend/.venv를 사용한다.
루트 .venv가 있더라도 혼동하지 않는다.
명령은 cd backend 후 source .venv/bin/activate를 전제로 한다.
```

직접 실행:

```bash
cd backend
source .venv/bin/activate
python --version
python -m uvicorn app.main:app --reload --port 8000
```

확인:

```bash
curl http://localhost:8000/health
```

8000번 포트가 이미 사용 중일 때만 임시로 8001을 쓴다.

```bash
python -m uvicorn app.main:app --reload --port 8001
```

## 002. DB 연결 skeleton 채우기

목표:

```text
PostgreSQL 연결 설정을 backend/app/db.py에 추가한다.
```

만질 파일:

```text
backend/app/db.py
backend/requirements.txt
.env.example
```

완료 기준:

```text
DATABASE_URL을 읽을 수 있다.
SQLAlchemy engine과 SessionLocal을 만들 수 있다.
Base와 get_db()가 정의된다.
아직 테이블 생성이나 데이터 저장은 하지 않는다.
DB가 꺼져 있어도 /health는 깨지지 않는다.
```

DATABASE_URL 예시:

```text
DATABASE_URL=postgresql+psycopg://localhost:5432/corporate_memory
```

의미:

```text
FastAPI 앱이 SQLAlchemy를 통해 PostgreSQL의 corporate_memory 데이터베이스에 연결하기 위한 주소다.
002에서는 연결 준비만 하고, 테이블 생성과 저장 로직은 만들지 않는다.
```

## 003. SQLAlchemy models 정의

목표:

```text
5개 테이블의 ORM 모델을 정의한다.
```

만질 파일:

```text
backend/app/models.py
backend/app/db.py
```

완료 기준:

```text
companies, earnings_calls, transcripts, chunks, claims 모델이 있다.
아직 실제 ingest 저장 로직은 만들지 않는다.
```

## 004. Pydantic schemas 정리

목표:

```text
POST /ingest/transcript 요청/응답 타입을 명확히 한다.
```

만질 파일:

```text
backend/app/schemas.py
backend/app/routers/ingest.py
```

완료 기준:

```text
TranscriptIngestRequest와 TranscriptIngestResponse가 요청/응답 예시에 맞는다.
POST /ingest/transcript는 아직 skeleton 응답을 반환한다.
```

## 005. Transcript metadata 저장

목표:

```text
company, earnings_call, transcript까지만 DB에 저장한다.
```

만질 파일:

```text
backend/app/routers/ingest.py
backend/app/db.py
backend/app/models.py
```

완료 기준:

```text
POST /ingest/transcript 호출 시 companies, earnings_calls, transcripts에 데이터가 저장된다.
chunks와 claims는 아직 저장하지 않는다.
```

## 006. chunker 구현

목표:

```text
Transcript 원문을 section / speaker 기준 chunk list로 나눈다.
```

만질 파일:

```text
backend/app/services/chunker.py
```

완료 기준:

```text
chunk_transcript(raw_text)가 list[dict]를 반환한다.
DB 저장은 아직 하지 않는다.
```

## 007. chunks 저장

목표:

```text
chunk_transcript 결과를 chunks 테이블에 저장한다.
```

만질 파일:

```text
backend/app/routers/ingest.py
backend/app/models.py
backend/app/services/chunker.py
```

완료 기준:

```text
Transcript 1개 입력 시 chunks가 여러 개 저장된다.
claims는 아직 저장하지 않는다.
```

## 008. claim_extractor 구현

목표:

```text
OpenAI API 없이 규칙 기반으로 claim 후보 문장을 뽑는다.
```

만질 파일:

```text
backend/app/services/claim_extractor.py
```

완료 기준:

```text
extract_claims(chunk_text)가 claim 후보 list[dict]를 반환한다.
DB 저장은 아직 하지 않는다.
```

## 009. claims 저장

목표:

```text
extract_claims 결과를 claims 테이블에 저장한다.
```

만질 파일:

```text
backend/app/routers/ingest.py
backend/app/models.py
backend/app/services/claim_extractor.py
```

완료 기준:

```text
Transcript 1개 입력 시 claims가 저장된다.
```

## 010. End-to-end count 반환

목표:

```text
POST /ingest/transcript가 저장된 id와 count를 반환한다.
```

만질 파일:

```text
backend/app/routers/ingest.py
```

완료 기준:

```text
응답에 company_id, call_id, transcript_id, chunk_count, claim_count가 실제 값으로 나온다.
```

## 아직 하지 않을 것

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
