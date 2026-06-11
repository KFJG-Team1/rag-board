# PR Atlas PostgreSQL Import 탑다운 읽기

이 문서는 현재 `pr_atlas_mvp` 코드를 파일 순서대로 설명하지 않습니다. 먼저 최종 저장 결과와 데이터 구조를 보고, 그 결과를 만들기 위해 실행 흐름이 어떻게 내려가는지 Mermaid 구조도 중심으로 읽습니다.

## 0. 최종 저장 결과 먼저 보기

현재 목표는 GitHub PR 하나 또는 PR 목록 페이지를 가져와 파싱하고, PostgreSQL에 충돌 분석용 기초 데이터를 실제로 저장하는 것입니다.

```mermaid
flowchart TD
    CLI["import_pr_to_postgres.py<br/>CLI 입력"]
    MODE["--pr 또는 --batch<br/>대상 PR 번호 결정"]
    FETCH["parsing.runner.fetch_import_batch<br/>GitHub 수집 + 정규화"]
    BATCH["ImportBatch<br/>내부 표준 데이터"]
    STORE["postgres.store.store_import_batch<br/>트랜잭션 저장"]

    CLI --> MODE --> FETCH --> BATCH --> STORE

    STORE --> REPO["repositories"]
    STORE --> PR["pull_requests"]
    STORE --> PATH["file_paths"]
    STORE --> FILE["pr_files"]
    STORE --> HUNK["pr_file_hunks"]
    STORE --> RAW["raw_payloads"]
```

최종적으로 중요한 데이터는 두 가지입니다.

```text
1. 파싱 결과:
   PR마다 ImportBatch 하나

2. DB 저장 결과:
   PR마다 StoreResult(repo_key, pr_key, file_count, hunk_count)
```

### ImportBatch 예시

```json
{
  "repository": {
    "id": "R_kgDOExample",
    "owner": "octocat",
    "name": "hello-world"
  },
  "pull_request": {
    "number": 42,
    "title": "Fix user profile response",
    "url": "https://github.com/octocat/hello-world/pull/42",
    "state": "OPEN",
    "base_ref": "main",
    "head_ref": "fix-user-profile-response",
    "base_sha": "3f4a0c1b9e2d",
    "head_sha": "9b8c7d6e5f4a",
    "updated_at": "2026-06-10T08:15:30Z",
    "labels": ["api", "bug"],
    "files": [
      {
        "path": "src/api/users.py",
        "path_tree": "src.api.users.py",
        "status": "modified",
        "additions": 12,
        "deletions": 3,
        "changes": 15,
        "hunks": [
          {
            "header": "@@ -10,7 +10,12 @@ def get_user(user_id):",
            "old_start": 10,
            "old_lines": 7,
            "new_start": 10,
            "new_lines": 12,
            "lines": [
              {
                "type": "add",
                "content": "    return {\"name\": user.name, \"avatarUrl\": user.avatar_url}",
                "old_line": null,
                "new_line": 11
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### StoreResult 예시

```text
StoreResult(
  repo_key="R_kgDOExample",
  pr_key="R_kgDOExample#42",
  file_count=1,
  hunk_count=1
)
```

## 1. 현재 폴더 구조

루트에는 실행 진입점만 남기고, 파싱과 DB 저장 책임은 하위 패키지로 분리했습니다.

```mermaid
flowchart TD
    ROOT["pr_atlas_mvp"]
    MAIN["import_pr_to_postgres.py<br/>CLI 진입점"]
    PARSING["parsing/<br/>GitHub 수집, 정규화, patch 파싱"]
    POSTGRES["postgres/<br/>연결, 스키마, 저장 쿼리"]

    ROOT --> MAIN
    ROOT --> PARSING
    ROOT --> POSTGRES

    PARSING --> RUNNER["runner.py"]
    PARSING --> GITHUB["github_client.py"]
    PARSING --> MODELS["models.py"]
    PARSING --> NORMALIZER["normalizer.py"]
    PARSING --> PATCH["patch_parser.py"]
    PARSING --> PLAN["db_plan.py"]
    PARSING --> PRINTER["printer.py"]

    POSTGRES --> CONN["connection.py"]
    POSTGRES --> SCHEMA["schema.py"]
    POSTGRES --> STORE["store.py"]
    POSTGRES --> WRITES["writes.py"]
```

`parsing/db_plan.py`과 `parsing/printer.py`는 이전 출력 중심 MVP의 보조 코드로 남아 있습니다. 현재 실행 진입점은 이 둘을 사용하지 않고 DB 저장 경로로 바로 갑니다.

## 2. 전체 실행 흐름

```mermaid
flowchart TD
    CLI["python -m pr_atlas_mvp.import_pr_to_postgres"]
    ENV["load_local_env<br/>.env 로드"]
    ARGS["parse_args<br/>owner, repo, --pr/--batch, database-url"]
    TOKEN["get_github_token<br/>GITHUB_TOKEN"]
    DBURL["get_database_url<br/>DATABASE_URL"]
    TARGETS["대상 PR 번호 목록 결정"]
    ONE["--pr<br/>번호 1개"]
    MANY["--batch<br/>fetch_pr_numbers_rest"]
    LOOP["for pr_number in pr_numbers"]

    FETCH["fetch_import_batch"]
    GQL["fetch_pr_graphql<br/>changedFiles cursor pagination"]
    REST["fetch_pr_files_rest<br/>REST page pagination"]
    NORMALIZE["normalize_import_batch"]
    CONNECT["connect_database"]
    SAVE["store_import_batch"]

    CLI --> ENV --> ARGS --> TOKEN --> DBURL
    DBURL --> CONNECT
    DBURL --> TARGETS
    TARGETS --> ONE --> LOOP
    TARGETS --> MANY --> LOOP
    LOOP --> FETCH
    FETCH --> GQL
    FETCH --> REST
    GQL --> NORMALIZE
    REST --> NORMALIZE
    NORMALIZE --> SAVE
    CONNECT --> SAVE
```

```text
실행 파일은 CLI/env/DB 연결만 관리한다.
--pr은 PR 번호 하나를 저장하고, --batch는 REST PR 목록 페이지에서 여러 번호를 가져와 순서대로 저장한다.
GitHub 수집과 정규화는 parsing 패키지에서 끝낸다.
PostgreSQL 저장은 postgres 패키지에서 트랜잭션으로 처리한다.
```

## 3. 실행 시퀀스

```mermaid
sequenceDiagram
    autonumber
    actor User as 사용자
    participant Main as import_pr_to_postgres.py
    participant Runner as parsing/runner.py
    participant GitHub as parsing/github_client.py
    participant Norm as parsing/normalizer.py
    participant Patch as parsing/patch_parser.py
    participant Conn as postgres/connection.py
    participant Store as postgres/store.py
    participant Writes as postgres/writes.py

    User->>Main: python -m pr_atlas_mvp.import_pr_to_postgres --owner --repo --pr 또는 --batch
    Main->>Main: load_local_env()
    Main->>Main: parse_args()
    Main->>Main: get_github_token()
    Main->>Main: get_database_url()
    alt --pr
        Main->>Main: pr_numbers = [args.pr]
    else --batch
        Main->>GitHub: fetch_pr_numbers_rest(owner, repo, state, page, limit)
        GitHub-->>Main: list[int]
    end
    Main->>Conn: connect_database(database_url)
    loop pr_number in pr_numbers
        Main->>Runner: fetch_import_batch(owner, repo, pr_number, token)
        Runner->>GitHub: fetch_pr_graphql(owner, repo, pr_number, token)
        loop while changedFiles.pageInfo.hasNextPage
            GitHub->>GitHub: fetch_pr_graphql_page(after=endCursor)
            GitHub->>GitHub: changedFiles.nodes 누적
        end
        GitHub-->>Runner: graphql_repository
        Runner->>GitHub: fetch_pr_files_rest(owner, repo, pr_number, token)
        GitHub-->>Runner: rest_files
        Runner->>Norm: normalize_import_batch(owner, repo, graphql_repository, rest_files)
        Norm->>Patch: parse_patch(file.patch)
        Patch-->>Norm: list[DiffHunk]
        Norm-->>Runner: ImportBatch
        Runner-->>Main: ImportBatch
        Main->>Store: store_import_batch(conn, batch)
        Store->>Writes: upsert_repository()
        Store->>Writes: upsert_pull_request()
        Store->>Writes: delete_pr_file_snapshot()
        Store->>Writes: upsert_raw_payload()
        Store->>Writes: insert_pr_file()
        Store->>Writes: insert_pr_file_hunk()
        Store-->>Main: StoreResult
    end
```

## 4. 내부 데이터 모델

`parsing/models.py`는 GitHub 응답을 프로젝트 내부에서 다루는 표준 형태로 정의합니다.

```mermaid
classDiagram
    class ImportBatch {
        repository
        pull_request
    }

    class PullRequestSnapshot {
        number
        title
        url
        state
        base_ref
        head_ref
        base_sha
        head_sha
        updated_at
        labels
        files
        raw_graphql
    }

    class PullRequestFile {
        path
        path_tree
        status
        additions
        deletions
        changes
        patch
        hunks
        raw_rest
    }

    class DiffHunk {
        header
        old_start
        old_lines
        new_start
        new_lines
        lines
    }

    class DiffLine {
        type
        content
        old_line
        new_line
    }

    ImportBatch --> PullRequestSnapshot : pull_request
    PullRequestSnapshot --> PullRequestFile : files
    PullRequestFile --> DiffHunk : hunks
    DiffHunk --> DiffLine : lines
```

데이터의 깊이는 PR에서 파일로, 파일에서 hunk로, hunk에서 line으로 내려갑니다.

```text
PR 하나
  -> 변경 파일 여러 개
    -> 파일별 diff hunk 여러 개
      -> hunk 안의 add/delete/context line 여러 개
```

## 5. 파싱 패키지 책임

```mermaid
flowchart LR
    Runner["parsing/runner.py<br/>fetch_import_batch"]
    GitHub["parsing/github_client.py<br/>GraphQL + REST 요청"]
    Normalizer["parsing/normalizer.py<br/>응답 병합과 모델 생성"]
    Patch["parsing/patch_parser.py<br/>patch 문자열 파싱"]
    Models["parsing/models.py<br/>dataclass"]

    Runner --> GitHub
    Runner --> Normalizer
    Normalizer --> Patch
    Normalizer --> Models
    Patch --> Models
```

`fetch_import_batch()`는 `ImportBatch`를 만드는 경계 함수입니다. DB 코드는 GitHub API나 patch 문자열을 직접 알 필요가 없습니다.

### GitHub 수집 세부 흐름

```mermaid
flowchart TD
    START["fetch_import_batch"]
    GQL["fetch_pr_graphql"]
    GQL_PAGE["fetch_pr_graphql_page<br/>files(first: 100, after: cursor)"]
    GQL_MORE{"hasNextPage?"}
    GQL_MERGE["changedFiles.nodes 누적"]
    REST["fetch_pr_files_rest"]
    REST_PAGE["GET /pulls/{pr}/files<br/>per_page=100&page=n"]
    REST_MORE{"응답 개수 == 100?"}
    NORMALIZE["normalize_import_batch"]

    START --> GQL --> GQL_PAGE --> GQL_MORE
    GQL_MORE -- yes --> GQL_MERGE --> GQL_PAGE
    GQL_MORE -- no --> REST
    REST --> REST_PAGE --> REST_MORE
    REST_MORE -- yes --> REST_PAGE
    REST_MORE -- no --> NORMALIZE
```

GraphQL 응답은 PR 메타데이터와 파일별 `path`, `additions`, `deletions`, `changeType`을 가져옵니다. `changedFiles`는 최대 100개 단위로 오기 때문에 `pageInfo.endCursor`를 다음 요청의 `after`로 넘기고, `hasNextPage`가 `false`가 될 때까지 `nodes`를 합칩니다.

REST 응답은 파일별 `patch` 문자열을 가져옵니다. 이 값이 있어야 `patch_parser.py`가 diff hunk와 line 정보를 만들 수 있습니다.

## 6. PostgreSQL 스키마

`postgres/schema.py`는 `ltree` extension, 테이블, 인덱스를 만듭니다.

이 스키마는 단순히 GitHub 응답을 펼쳐 저장하는 구조가 아닙니다. 핵심 기준은 **데이터가 어떤 수명과 역할을 가지는가**입니다.

```mermaid
flowchart TD
    Repo["repositories<br/>저장소 자체"]
    PathLayer["file_paths<br/>저장소 경로 지도 레이어"]
    PR["pull_requests<br/>PR 메타데이터"]
    PRFile["pr_files<br/>특정 PR이 경로 위에 남긴 변경 이벤트"]
    Hunk["pr_file_hunks<br/>변경 이벤트의 라인 범위"]
    Raw["raw_payloads<br/>GitHub 원본 응답 보관"]

    Repo --> PathLayer
    Repo --> PR
    PR --> PRFile
    PathLayer --> PRFile
    PRFile --> Hunk
    PR --> Raw
    PRFile --> Raw
```

`file_paths`는 `pr_files`와 비슷한 값을 저장하기 위해 만든 중복 테이블이 아닙니다. 이 테이블은 나중에 UI에서 반투명한 저장소 경로 지도를 깔고, 그 위에 여러 PR 변경 흐름을 표시하기 위한 기준 레이어입니다.

```mermaid
flowchart TD
    subgraph BaseLayer["고정에 가까운 배경 레이어"]
        FP["file_paths<br/>path<br/>path_tree"]
    end

    subgraph EventLayer["PR별 변경 이벤트 레이어"]
        PF1["PR #10 -> src/api/users.py<br/>additions/deletions/patch"]
        PF2["PR #24 -> src/api/users.py<br/>additions/deletions/patch"]
        PF3["PR #31 -> src/api/auth.py<br/>additions/deletions/patch"]
    end

    FP --> PF1
    FP --> PF2
    FP --> PF3
```

따라서 현재 구조에서 `file_paths`와 `pr_files`의 관계는 다음처럼 해석합니다.

```text
file_paths:
  저장소 안의 파일 경로 자체를 나타내는 지도 레이어
  같은 파일이 여러 PR에서 반복 변경될 때 공통 기준점이 된다.
  나중에 파일별 risk_score, owner, module, 시각화 좌표를 붙일 수 있다.

pr_files:
  특정 PR이 특정 파일 경로 위에서 만든 변경 이벤트
  additions, deletions, status, patch, raw_rest처럼 PR snapshot에 종속되는 값이 들어간다.
```

`raw_payloads`는 정규화된 테이블만으로 설명되지 않는 GitHub 원본 응답을 보존하는 보조 저장소입니다. 현재 `pull_requests.raw_graphql`, `pr_files.raw_rest`에도 원본 일부를 들고 있으므로 단순성만 보면 중복이지만, 나중에 정규화 로직 변경, API 응답 검증, 재처리, 디버깅을 위해 원본 payload를 entity/source 기준으로 따로 남기는 역할을 합니다.

```mermaid
erDiagram
    REPOSITORIES ||--o{ PULL_REQUESTS : contains
    REPOSITORIES ||--o{ FILE_PATHS : owns
    PULL_REQUESTS ||--o{ PR_FILES : changes
    FILE_PATHS ||--o{ PR_FILES : referenced_by
    PR_FILES ||--o{ PR_FILE_HUNKS : has

    REPOSITORIES {
        bigint id PK
        text repo_key UK
        text owner
        text name
    }

    PULL_REQUESTS {
        bigint id PK
        text pr_key UK
        bigint repository_id FK
        int number
        text title
        text state
        text base_ref
        text head_ref
        text head_sha
        text_array labels
        jsonb raw_graphql
    }

    FILE_PATHS {
        bigint id PK
        bigint repository_id FK
        text path
        ltree path_tree
    }

    PR_FILES {
        bigint id PK
        text pr_file_key UK
        bigint pull_request_id FK
        bigint file_path_id FK
        text path
        ltree path_tree
        text status
        int additions
        int deletions
        int changes
        text patch
        jsonb raw_rest
    }

    PR_FILE_HUNKS {
        bigint id PK
        text hunk_key UK
        bigint pr_file_id FK
        int hunk_index
        int old_start
        int old_lines
        int new_start
        int new_lines
        jsonb hunk_json
    }

    RAW_PAYLOADS {
        bigint id PK
        text entity_type
        text entity_key
        text source
        jsonb payload
    }
```

현재 `pr_files`에는 `file_path_id`가 있으면서도 `path`, `path_tree`가 같이 저장됩니다. 이 값들은 `file_paths`와 겹치지만, 지금 단계에서는 다음 이유로 유지합니다.

```text
1. PR 파일 목록을 조회할 때 join 없이 path를 바로 표시할 수 있다.
2. PR snapshot 당시 GitHub가 내려준 경로를 pr_files에 보존한다.
3. path_tree 기반 디렉토리 필터를 pr_files에서 바로 수행할 수 있다.
4. file_paths는 장기적으로 지도 레이어 역할을 하고,
   pr_files는 그 지도 위의 PR별 변경 이벤트 역할을 한다.
```

나중에 스키마를 더 엄격하게 정규화하려면 `pr_files.path`, `pr_files.path_tree`를 제거하고 `file_path_id`만 남길 수 있습니다. 하지만 현재 MVP에서는 조회 편의성과 snapshot 보존을 위해 중복을 허용합니다.

인덱스는 두 종류의 조회를 의식합니다.

```text
1. path_tree LTREE 검색:
   특정 디렉토리 아래 변경 파일 찾기

2. int4range(new_start, new_start + new_lines) GIST 검색:
   같은 파일 안에서 hunk range overlap 찾기
```

## 7. 저장 트랜잭션 구조

`postgres/store.py`는 `ImportBatch` 하나를 저장하는 순서를 고정합니다. `--batch`일 때도 저장 단위는 PR 하나의 `ImportBatch`이고, CLI가 이 함수를 PR 번호마다 반복 호출합니다.

```mermaid
flowchart TD
    Batch["ImportBatch"]
    Schema["ensure_schema<br/>optional"]
    TX["session.begin"]
    Repo["upsert_repository"]
    PR["upsert_pull_request"]
    Delete["delete_pr_file_snapshot<br/>같은 PR 재수입 대비"]
    RawPR["upsert_raw_payload<br/>github_graphql"]
    FileLoop["for file in pr.files"]
    Path["upsert_file_path"]
    PRFile["insert_pr_file"]
    RawFile["upsert_raw_payload<br/>github_rest"]
    HunkLoop["for hunk in file.hunks"]
    Hunk["insert_pr_file_hunk"]
    Result["StoreResult"]

    Batch --> Schema --> TX --> Repo --> PR --> Delete --> RawPR --> FileLoop
    FileLoop --> Path --> PRFile --> RawFile --> HunkLoop --> Hunk
    Hunk --> Result
```

재수입 정책은 단순합니다.

```text
같은 PR을 다시 가져오면:
  pull_requests row는 upsert
  pr_files와 pr_file_hunks는 기존 snapshot 삭제 후 새로 insert
  raw_payloads는 entity key 기준으로 upsert
```

`--batch`에서는 첫 번째 PR 저장 때만 `create_schema=True`가 됩니다. 두 번째 PR부터는 같은 테이블을 재사용하므로 `--skip-schema`와 같은 효과로 저장만 수행합니다.

## 8. 실행 방법

`.env`에는 최소한 두 값이 필요합니다.

```sh
GITHUB_TOKEN=github_pat_xxx
DATABASE_URL=postgresql://user:password@localhost:5432/pr_atlas
```

PR 하나만 가져오는 실행 명령은 다음입니다.

```sh
python3 -m pr_atlas_mvp.import_pr_to_postgres --owner python --repo cpython --pr 123456
```

여러 PR을 한 번에 가져오려면 `--batch`를 씁니다. 이 명령은 GitHub REST PR 목록에서 지정한 `state`, `page`, `limit`에 해당하는 PR 번호들을 가져온 뒤, 각 PR을 같은 저장 로직으로 순서대로 저장합니다.

```sh
python3 -m pr_atlas_mvp.import_pr_to_postgres --owner python --repo cpython --batch --state all --page 1 --limit 100
```

이미 스키마가 준비된 DB에 저장만 하고 싶으면 다음 옵션을 씁니다.

```sh
python3 -m pr_atlas_mvp.import_pr_to_postgres --owner python --repo cpython --pr 123456 --skip-schema
```

```sh
python3 -m pr_atlas_mvp.import_pr_to_postgres --owner python --repo cpython --batch --skip-schema
```

## 9. 코드 읽는 순서

```mermaid
flowchart TD
    A["1. import_pr_to_postgres.py<br/>CLI/env/DB 연결"]
    B["2. parsing/runner.py<br/>ImportBatch 생성 경계"]
    C["3. parsing/models.py<br/>내부 데이터 구조"]
    D["4. parsing/github_client.py<br/>GitHub API 수집"]
    E["5. parsing/normalizer.py<br/>응답 병합"]
    F["6. parsing/patch_parser.py<br/>patch -> hunk"]
    G["7. postgres/schema.py<br/>테이블과 인덱스"]
    H["8. postgres/store.py<br/>저장 순서"]
    I["9. postgres/writes.py<br/>실제 SQL"]

    A --> B --> C --> D --> E --> F --> G --> H --> I
```

먼저 `ImportBatch` 구조를 잡고 나면, DB 저장 코드는 `ImportBatch`를 어떤 테이블에 어떤 순서로 풀어 넣는지로 읽으면 됩니다.

## 10. 현재 구현의 경계

```mermaid
flowchart LR
    subgraph Done["현재 구현됨"]
        D1["PR 하나 import"]
        D2["GraphQL PR metadata 수집"]
        D3["GraphQL changedFiles pagination 완료 처리"]
        D4["REST files and patch pagination 수집"]
        D5["여러 PR batch import"]
        D6["ImportBatch 정규화"]
        D7["patch hunk 파싱"]
        D8["PostgreSQL schema 생성"]
        D9["PostgreSQL INSERT/UPSERT"]
    end

    subgraph NotYet["아직 구현 안 됨"]
        N1["저장소 전체 PR 페이지 자동 순회"]
        N2["PR pair risk scoring"]
        N3["semantic analysis"]
        N4["UI 시각화"]
    end
```

현재 구현은 PostgreSQL 기반 Repository Import의 MVP입니다.

```text
단일 PR 또는 PR 목록 페이지를 가져와 충돌 분석에 필요한 파일, hunk,
원본 payload를 PostgreSQL에 저장하는 것까지 수행한다.
```
