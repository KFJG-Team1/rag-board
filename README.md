# AI 월드컵 선수 정보 게시판

## 프로젝트 개요

AI 월드컵 선수 정보 게시판은 월드컵을 시청하는 사용자를 위한 축구 정보 플랫폼이다.

사용자는 경기 일정, 국가별 선수 정보, 선수 검색 기능을 이용할 수 있으며, 게시판을 통해 경기와 선수에 대한 의견을 공유할 수 있다.

또한 MCP(Model Context Protocol), RAG(Retrieval-Augmented Generation), Agent 기술을 활용하여 자연어 기반 선수 검색 및 축구 정보 질의응답 기능을 제공하는 것을 목표로 한다.

---

# 프로젝트 목표

## 사용자 문제

월드컵 시청 중 다음과 같은 상황이 자주 발생한다.

* 한국 경기 일정이 궁금하다.
* 특정 선수의 소속팀이나 국가대표 정보를 알고 싶다.
* 국가별 선수 명단을 확인하고 싶다.
* 특정 경기와 관련된 사람들의 의견을 보고 싶다.
* 선수에 대한 설명을 자연어로 듣고 싶다.

현재는 여러 사이트를 이동하며 정보를 찾아야 하지만, 본 프로젝트는 하나의 서비스 안에서 이를 해결하는 것을 목표로 한다.

---

# MVP 범위

## 경기 일정 조회

사용자는 국가명을 입력하여 해당 국가의 경기 일정을 조회할 수 있다.

예시

```text
한국 경기 일정 알려줘

↓

South Korea vs Uruguay
South Korea vs Ghana
South Korea vs Portugal
```

---

## 국가별 선수 조회

국가명을 입력하여 해당 국가 선수 명단을 조회할 수 있다.

예시

```text
브라질 선수 알려줘
```

↓

```text
브라질 국가대표 선수 목록
```

---

## 선수 검색

선수 이름 검색 기능 제공

지원 기능

* 부분 검색
* 대소문자 무시
* 공백 무시
* 하이픈 무시

예시

```text
son
heung
sonheungmin
```

↓

```text
Son Heung-Min
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

* 생성
* 검색
* 게시글 분류

---

## 검색

* 제목 검색
* 내용 검색
* 태그 검색

---

## 페이징

게시글 목록 페이지네이션 지원

---

# 확장 기능

## 경기 상세 페이지

경기 정보

* 경기 날짜
* 경기 시간
* 경기장
* 홈팀
* 원정팀

관련 게시글 표시

---

## 선수 상세 페이지

선수 정보

* 이름
* 국가
* 포지션
* 등번호
* 소속팀
* 리그
* 생년월일
* 키
* 몸무게
* 사진

---

## 등번호 검색

예시

```text
한국 7번 누구야?
```

↓

```text
Son Heung-Min
```

---

## 현재 경기 정보

홈 화면에서 진행 중인 경기 표시

예시

```text
현재 경기

Brazil vs Argentina
```

---

# AI 기능

## MCP

### 목적

외부 축구 데이터를 LLM이 사용할 수 있도록 Tool 제공

### Tool 목록

```text
search_players
get_team_players
get_match_schedule
```

### 예시

```text
손흥민 정보 알려줘
```

↓

```text
search_players 호출
```

---

## RAG

### 목적

게시판 데이터와 선수 정보를 검색하여 LLM 답변 생성

### 데이터

* 선수 정보
* 경기 정보
* 게시글
* 댓글

### 예시

```text
손흥민 어떤 선수야?
```

↓

```text
선수 정보 검색

+

관련 게시글 검색

+

답변 생성
```

---

## Agent

### 목적

사용자 질문을 분석하여 적절한 Tool 선택

### 예시

```text
한국 경기 일정 알려줘
```

↓

```text
Agent

↓

get_match_schedule 호출
```

---

# 데이터 전략

## 외부 데이터

### API-Football

수집 데이터

* 경기 일정
* 국가 정보
* 선수 정보

---

## 내부 데이터

PostgreSQL 저장

* 사용자
* 게시글
* 댓글
* 태그

---

## Fallback 전략

외부 API 실패 시

* 더미 데이터 사용
* 이후 DB 캐시 사용 예정

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

## Environment

* Python 3.x
* Pydantic Settings
* Requests

---

# 아키텍처

```text
사용자

↓

React

↓

FastAPI

↓

Service Layer

↓

Repository Layer

├── PostgreSQL
├── API-Football
└── Vector DB

↓

MCP Server

↓

Agent

↓

OpenAI
```

---

# 예상 DB 테이블

## users

```text
id
email
password
nickname
created_at
```

---

## posts

```text
id
user_id
title
content
created_at
updated_at
```

---

## comments

```text
id
post_id
user_id
content
created_at
```

---

## tags

```text
id
name
```

---

## post_tags

```text
post_id
tag_id
```

---

## players

```text
id
name
country
position
number
club
league
birth_date
height_cm
weight_kg
image_url
```

---

## matches

```text
id
date
time
home_team
away_team
stadium
```

---

# 개발 순서

## 1단계

* 외부 축구 API 연동
* MCP Tool 구축

## 2단계

* FastAPI 구축
* PostgreSQL 연결

## 3단계

* 게시판 CRUD
* 댓글
* 태그
* 검색
* 페이징

## 4단계

* React UI 구현

## 5단계

* RAG 구축

## 6단계

* Agent 구축

## 7단계

* 서비스 고도화
* 등번호 검색
* 현재 경기 표시
* 경기 상세 페이지

```
```
