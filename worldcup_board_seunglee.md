# AI 월드컵 선수 정보 게시판

## 프로젝트 소개

월드컵을 시청하는 사용자가 경기 일정과 선수 정보를 쉽게 조회하고, 경기 관련 의견을 공유할 수 있는 AI 기반 축구 정보 게시판입니다.

단순 게시판을 넘어 MCP(Model Context Protocol), 외부 축구 API, RAG를 활용하여 자연어 기반 선수 검색 및 경기 정보 조회 기능을 제공하는 것을 목표로 합니다.

---

# 프로젝트 목표

### 사용자 문제

월드컵 시청 중 다음과 같은 궁금증이 자주 발생한다.

* 한국 경기 언제 하지?
* 손흥민은 어느 리그에서 뛰고 있지?
* 브라질 선수 명단 좀 보여줘
* 이 경기 관련 사람들은 어떤 의견을 가지고 있지?

기존에는 여러 사이트를 오가며 정보를 찾아야 한다.

본 프로젝트는 경기 정보, 선수 정보, 게시판 토론을 하나의 서비스에서 제공하는 것을 목표로 한다.

---

# 주요 기능

## 경기 일정 조회

* 국가별 경기 일정 조회
* 경기 날짜 조회
* 경기장 정보 조회

예시

```text
한국 경기 일정 알려줘

↓

2022-11-24
Uruguay vs South Korea

2022-11-28
South Korea vs Ghana
```

---

## 선수 검색

* 선수 이름 검색
* 부분 검색 지원
* 대소문자 무시
* 공백 및 하이픈 무시

예시

```text
heung
SON
sonheungmin
```

↓

```text
Son Heung-Min
```

---

## 국가별 선수 조회

예시

```text
한국 선수 알려줘
브라질 선수 명단 보여줘
```

↓

```text
선수 목록 반환
```

---

## 게시판

### 게시글

* 생성(Create)
* 조회(Read)
* 수정(Update)
* 삭제(Delete)

### 댓글

* 생성(Create)
* 조회(Read)
* 수정(Update)
* 삭제(Delete)

### 태그

* 태그 등록
* 태그 검색

---

# AI 기능

## MCP

축구 정보를 조회하는 Tool 제공

### Tool 목록

```text
search_players
get_team_players
get_match_schedule
```

### 예시

```text
손흥민 정보 알려줘

↓

search_players
```

---

## RAG

게시판 데이터와 선수 정보를 활용한 검색 기능

예시

```text
손흥민 어떤 선수야?
```

↓

```text
선수 정보 검색
+
게시판 정보 검색
+
LLM 응답 생성
```

---

## Agent

사용자 질문을 분석하여 적절한 Tool을 선택

예시

```text
한국 경기 일정 알려줘
```

↓

```text
get_match_schedule 호출
```

---

# 기술 스택

## Frontend

* React

## Backend

* FastAPI
* Python

## Database

* PostgreSQL

## AI

* OpenAI API
* LangChain
* MCP

## External API

* API-Football

---

# 프로젝트 구조

```text
app/
├── core/
│   └── config.py
│
├── football/
│   ├── player_data.py
│   ├── match_data.py
│   ├── repository.py
│   ├── service.py
│   └── external_api.py
│
├── mcp_server/
│   ├── server.py
│   └── tools.py
│
└── main.py
```

---

# 데이터 흐름

## 경기 일정 조회

```text
사용자
↓
MCP Tool
↓
service.py
↓
repository.py
↓
API-Football
↓
결과 반환
```

---

## 선수 검색

```text
사용자
↓
MCP Tool
↓
service.py
↓
API-Football

실패 시

↓
더미 데이터
↓
결과 반환
```

---

# 개발 원칙

* 기능 우선 구현
* 최소 기능(MVP) 우선
* Repository 패턴 적용
* Service 계층 분리
* MCP Tool 재사용
* 환경변수(.env) 사용
* API 실패 시 Fallback 제공
* 이후 단계에서 리팩토링 진행

```
```
