# PR Collision Atlas 기획서

## 1. 제품 한 줄 정의

PR Collision Atlas는 여러 Pull Request의 변경 흐름과 merge 위험을 repository의 파일/폴더 지도 위에 보여주는 **merge planning board**다.

이 제품은 GitHub PR 목록을 더 예쁘게 보여주는 도구가 아니다. 사용자가 merge 전에 어떤 PR들이 서로 영향을 주는지, 어떤 파일이 위험한지, 어떤 순서로 리뷰하거나 merge해야 하는지 판단하도록 돕는 제품이다.

상세 시스템 아키텍처는 `spec.md`, RAG/analysis 세부 설계는 `rag.md`를 기준으로 한다.

## 2. 제품 기준 경험

제품의 기준 경험은 다음 흐름이다.

1. 사용자가 로그인한다.
2. 첫 화면에서 repository별 게시판을 본다.
3. repository에 들어가면 Figma 같은 2D Path Atlas 캔버스가 열린다.
4. 캔버스에는 폴더와 파일이 지도처럼 배치되어 있다.
5. 가까운 의미의 폴더와 파일은 캔버스에서도 가깝게 배치된다.
6. 사이드바에는 PR 목록이 있다.
7. 사용자가 PR 하나를 선택하면 기존 파일/폴더 지도는 연한 회색으로 낮아진다.
8. 선택된 PR이 건드린 파일은 해당 PR 색상으로 강조된다.
9. 선택된 PR이 건드린 파일들은 선으로 연결된다.
10. 여러 PR을 선택하면 PR별 색상이 다른 overlay가 같은 지도 위에 중첩된다.
11. 사용자가 분석 버튼을 누르면 merge 위험도가 계산된다.
12. 위험 파일은 캔버스 위에서 빨간 파일명과 느낌표 아이콘으로 표시된다.
13. 위험 파일명을 누르면 상세 분석 페이지로 이동한다.
14. 상세 분석 페이지는 어떤 PR이 어떤 파일, hunk, line range, 코드 조각에서 문제를 만들 수 있는지 보여준다.
15. 분석 결과는 어떤 PR을 먼저 merge, rebase, review하면 좋은지 제안한다.

이 흐름이 제품 판단의 기준이다. 기능이 늘어나도 이 경험을 흐리면 안 된다.

## 3. 왜 필요한가

### PR 목록은 관계를 보여주지 못한다

GitHub의 PR 목록은 PR을 독립된 항목으로 보여준다. 하지만 실제 개발에서는 PR들이 파일, 폴더, API, migration, 설정, label, 변경 의도 기준으로 서로 연결된다.

예를 들어 다음 PR들이 동시에 열려 있다고 하자.

- `#1201` 로그인 리팩토링
- `#1215` 회원가입 API 수정
- `#1220` users 테이블 migration 추가
- `#1233` 프로필 페이지 UI 수정

제목은 다르지만 실제로는 `auth`, `users`, `profile API`, `migration` 흐름에서 연결될 수 있다. 이 관계는 PR 목록만으로는 보이지 않는다.

### 충돌에는 중요도가 있다

모든 충돌이 같은 위험은 아니다.

- README 문구 충돌
- 주석 변경 충돌
- import 순서 충돌
- 같은 파일의 서로 먼 hunk 변경
- 같은 함수 로직 변경
- 같은 API response 변경
- 같은 DB migration chain 변경
- 같은 production config 변경

사용자는 모든 충돌을 보고 싶은 것이 아니다. 사람이 봐야 할 위험한 충돌을 먼저 보고 싶다.

### merge 직전에야 위험을 아는 것은 늦다

merge conflict는 보통 merge하려는 순간에야 드러난다. 하지만 팀이 실제로 원하는 것은 conflict가 난 뒤 해결하는 것이 아니라, merge 전에 위험한 PR 조합과 파일을 미리 보는 것이다.

PR Collision Atlas는 이미 발생한 conflict를 자동 해결하는 제품이 아니라, merge 전에 위험을 보고 리뷰/merge 순서를 계획하게 하는 제품이다.

## 4. 핵심 사용자

### 오픈소스 메인테이너

PR이 많이 쌓인 repository에서 어떤 PR을 먼저 봐야 하는지, 어떤 PR들이 서로 영향을 줄 수 있는지 빠르게 파악하고 싶은 사람.

### 팀 리드 / 테크 리드

여러 개발자가 동시에 같은 코드베이스에서 작업할 때 특정 파일, 폴더, 기능 영역에 변경이 과도하게 몰리고 있는지 보고 싶은 사람.

### 리뷰어

리뷰할 PR이 많을 때 영향도가 높은 PR과 낮은 PR을 구분하고 싶은 사람.

### 개인 개발자

내 PR이 main에 들어가기 전에 다른 열린 PR과 부딪힐 가능성이 있는지 확인하고 싶은 사람.

## 5. 핵심 제품 가치

### merge 전에 위험을 본다

사용자는 merge 버튼을 누르기 전에 위험한 PR 조합과 파일을 볼 수 있다.

### 중요한 충돌만 우선순위화한다

단순히 "같은 파일을 수정했다"를 보여주는 데서 끝나지 않는다. 파일 종류, hunk 위치, 변경량, path category, semantic context를 바탕으로 사람이 먼저 봐야 할 위험을 구분한다.

### PR 흐름을 파일/폴더 지도 위에서 본다

repository의 파일과 폴더를 배경 지도로 두고, PR 변경 이벤트가 그 위에 어떻게 지나가는지 보여준다. 사용자는 PR 목록이 아니라 변경 지형을 본다.

### merge 순서와 리뷰 액션을 제안한다

분석 결과는 위험 파일만 보여주지 않는다. 어떤 PR을 먼저 merge해야 하는지, 어떤 PR은 rebase 후 다시 봐야 하는지, 어떤 파일은 사람이 직접 리뷰해야 하는지 제안한다.

## 6. 주요 화면

### Repository Board

로그인 후 처음 보는 화면이다. 사용자가 접근할 수 있는 repository를 게시판처럼 보여준다.

초기에는 repository 이름, owner, import된 PR 수, 변경 파일 수, 최근 갱신 시각, 분석 가능 여부를 보여준다.

### Path Atlas Canvas

repository에 들어갔을 때 보이는 핵심 화면이다.

폴더와 파일이 Figma 같은 2D 캔버스 위에 배치된다. 폴더는 그룹처럼 보이고, 파일은 노드처럼 보인다. 가까운 의미의 파일과 폴더는 캔버스에서도 가깝게 배치된다.

### PR Overlay

사이드바에서 PR을 선택하면 해당 PR이 건드린 파일이 색상으로 강조된다.

PR 하나를 선택하면 해당 PR 색상만 강조되고, 나머지 지도는 연한 회색으로 낮아진다. 여러 PR을 선택하면 PR별 색상이 다르게 중첩된다.

### Risk Analysis Overlay

분석 버튼을 누르면 위험 파일이 캔버스 위에서 빨간 파일명과 느낌표 아이콘으로 표시된다.

이 화면은 사용자가 "어디를 먼저 봐야 하는가"를 빠르게 판단하게 하는 것이 목적이다.

### File Detail

위험 파일을 클릭하면 상세 분석 페이지로 이동한다.

상세 페이지는 관련 PR, 위험 이유, hunk line range, patch excerpt, deterministic 근거, RAG 설명을 보여준다.

### Merge Recommendation

분석 결과는 merge/rebase/review 액션을 제안한다.

예를 들어 migration PR을 먼저 merge해야 하는지, API PR을 먼저 리뷰해야 하는지, consumer PR은 rebase 후 다시 분석해야 하는지 알려준다.

## 7. 현재까지 완료한 것

현재 완료된 마일스톤은 `GitHub PR Import Foundation`이다.

완료된 것:

- GitHub public repository 대상 PR import
- 단일 PR import
- REST PR 목록 페이지 기반 batch import
- GraphQL PR metadata 수집
- REST changed files와 patch 수집
- PR metadata, label, base/head branch, SHA 저장
- 파일 경로를 `path_tree`로 변환
- diff patch를 hunk line range로 파싱
- PostgreSQL schema 생성
- GitHub 원본 GraphQL/REST payload 보존

현재 source of truth 테이블:

| 테이블 | 역할 |
| --- | --- |
| `repositories` | repository 자체 |
| `pull_requests` | PR metadata snapshot |
| `file_paths` | repository의 파일 경로 기준 레이어 |
| `pr_files` | PR이 특정 파일 위에 남긴 변경 이벤트 |
| `pr_file_hunks` | diff hunk의 old/new line range |
| `raw_payloads` | GitHub GraphQL/REST 원본 응답 |

이 단계의 의미는 명확하다. 제품 화면과 RAG/analysis가 사용할 원천 데이터가 이미 쌓이기 시작했다.

## 8. 앞으로의 마일스톤

### 1. RAG / Analysis Pipeline

기존 import 데이터에서 분석용 문서를 만들고, semantic retrieval, deterministic risk, LLM explanation, merge recommendation을 생성한다.

세부 설계는 `rag.md`를 따른다.

### 2. Output Contract + API

frontend가 소비할 구조화 output을 만든다.

핵심 output은 canvas layout, PR overlay, risk analysis, file detail, merge recommendation이다.

전체 시스템 흐름과 API 위치는 `spec.md`를 따른다.

### 3. Frontend Path Atlas

repository board, Path Atlas canvas, PR sidebar, PR overlay, risk overlay, file detail 화면을 구현한다.

frontend는 분석 로직을 소유하지 않고, backend/RAG output을 사용자 경험으로 바꾼다.

### 4. Persisted Analysis / Report Board

분석 결과를 다시 열고 공유할 수 있게 저장한다.

이 단계에서 analysis history, report board, resolution note가 들어간다.

### 5. Future Code Suggestion Layer

설명과 함께 코드 수정 제안을 생성하는 기능은 후속 기능으로 분리한다.

초기 제품은 위험 분석과 merge/review 액션 제안에 집중한다. 코드 수정안 자동 적용은 하지 않는다.

## 9. 제품 원칙

### 프런트는 분석 결과를 보여준다

frontend는 risk score, vector retrieval, hunk overlap, merge 순서 판단을 직접 계산하지 않는다. frontend는 분석 결과를 캔버스와 상세 화면으로 표현한다.

### RAG는 목적이 아니라 판단 보조 수단이다

RAG는 제품의 목적이 아니다. RAG는 파일/폴더 의미 관계, 위험 설명, merge 제안을 만들기 위한 수단이다.

### LLM은 설명과 제안에 개입하지만 hard evidence를 무시하지 않는다

LLM은 semantic conflict 해석, merge 순서 제안, 자연어 설명에 개입한다. 하지만 같은 파일, hunk overlap, critical path 같은 deterministic 근거를 임의로 낮출 수 없다.

### 새 테이블은 필요해질 때 추가한다

초기에는 기존 import 테이블을 최대한 활용한다. embedding cache, 분석 결과 저장, layout 좌표 고정 같은 구체적 요구가 생겼을 때만 새 테이블을 추가한다.

### 중요한 충돌을 먼저 보여준다

모든 변경 관계를 같은 무게로 보여주지 않는다. docs-only 변경과 migration/API/auth/config 변경은 다르게 다룬다.

## 10. 이번 범위에서 제외할 것

현재 제품 범위에서 제외한다.

- 실제 merge 실행
- 자동 conflict resolution
- 코드 자동 수정
- private repository 지원
- GitHub App 설치 방식
- 모든 언어의 AST 기반 semantic merge 분석
- repository를 넘는 과거 사례 검색
- 사용자 수동 캔버스 배치 저장

이 항목들은 제품 방향과 충돌하지 않지만, 지금 단계의 핵심은 아니다.

## 11. 관련 문서

- `spec.md`: 전체 시스템 아키텍처, 데이터 흐름, 주요 컴포넌트, 큰 마일스톤
- `rag.md`: RAG/analysis 구현 아키텍처, LangGraph/LangChain 역할, 알고리즘, input/output contract
- `pr_atlas_mvp/lesson/TOP_DOWN_POSTGRES_IMPORT.md`: 현재 import foundation의 코드 읽기 문서
