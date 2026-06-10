# PR Atlas PostgreSQL Import 탑다운 읽기

이 문서는 현재 `pr_atlas_mvp` 코드를 파일 순서대로 설명하지 않습니다. 먼저 최종 저장 결과와 데이터 구조를 보고, 그 결과를 만들기 위해 실행 흐름이 어떻게 내려가는지 Mermaid 구조도 중심으로 읽습니다.

## 0. 최종 저장 결과 먼저 보기

현재 목표는 GitHub PR 하나를 가져와 파싱하고, PostgreSQL에 충돌 분석용 기초 데이터를 실제로 저장하는 것입니다.

```mermaid
flowchart TD
    CLI["import_pr_to_postgres.py<br/>CLI 입력"]
    FETCH["parsing.runner.fetch_import_batch<br/>GitHub 수집 + 정규화"]
    BATCH["ImportBatch<br/>내부 표준 데이터"]
    STORE["postgres.store.store_import_batch<br/>트랜잭션 저장"]

    CLI --> FETCH --> BATCH --> STORE

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
   ImportBatch

2. DB 저장 결과:
   StoreResult(repo_key, pr_key, file_count, hunk_count)
```

### ImportBatch 예시

```json
{
  "repository": {
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
  repo_key="octocat/hello-world",
  pr_key="octocat/hello-world#42",
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
    ARGS["parse_args<br/>owner, repo, pr, database-url"]
    TOKEN["get_github_token<br/>GITHUB_TOKEN"]
    DBURL["get_database_url<br/>DATABASE_URL"]

    FETCH["fetch_import_batch"]
    GQL["fetch_pr_graphql"]
    REST["fetch_pr_files_rest"]
    NORMALIZE["normalize_import_batch"]
    CONNECT["connect_database"]
    SAVE["store_import_batch"]

    CLI --> ENV --> ARGS --> TOKEN --> DBURL
    DBURL --> FETCH
    FETCH --> GQL
    FETCH --> REST
    GQL --> NORMALIZE
    REST --> NORMALIZE
    NORMALIZE --> CONNECT
    CONNECT --> SAVE
```

```text
실행 파일은 CLI/env/DB 연결만 관리한다.
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

    User->>Main: python -m pr_atlas_mvp.import_pr_to_postgres --owner --repo --pr
    Main->>Main: load_local_env()
    Main->>Main: parse_args()
    Main->>Main: get_github_token()
    Main->>Main: get_database_url()
    Main->>Runner: fetch_import_batch(owner, repo, pr, token)
    Runner->>GitHub: fetch_pr_graphql(owner, repo, pr, token)
    GitHub-->>Runner: graphql_repository
    Runner->>GitHub: fetch_pr_files_rest(owner, repo, pr, token)
    GitHub-->>Runner: rest_files
    Runner->>Norm: normalize_import_batch(owner, repo, graphql_repository, rest_files)
    Norm->>Patch: parse_patch(file.patch)
    Patch-->>Norm: list[DiffHunk]
    Norm-->>Runner: ImportBatch
    Runner-->>Main: ImportBatch
    Main->>Conn: connect_database(database_url)
    Main->>Store: store_import_batch(conn, batch)
    Store->>Writes: upsert_repository()
    Store->>Writes: upsert_pull_request()
    Store->>Writes: delete_pr_file_snapshot()
    Store->>Writes: insert_pr_file()
    Store->>Writes: insert_pr_file_hunk()
    Store-->>Main: StoreResult
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

## 6. PostgreSQL 스키마

`postgres/schema.py`는 `ltree` extension, 테이블, 인덱스를 만듭니다.

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

인덱스는 두 종류의 조회를 의식합니다.

```text
1. path_tree LTREE 검색:
   특정 디렉토리 아래 변경 파일 찾기

2. int4range(new_start, new_start + new_lines) GIST 검색:
   같은 파일 안에서 hunk range overlap 찾기
```

## 7. 저장 트랜잭션 구조

`postgres/store.py`는 `ImportBatch` 하나를 저장하는 순서를 고정합니다.

```mermaid
flowchart TD
    Batch["ImportBatch"]
    TX["conn.transaction"]
    Schema["ensure_schema<br/>optional"]
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

    Batch --> TX --> Schema --> Repo --> PR --> Delete --> RawPR --> FileLoop
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

## 8. 실행 방법

`.env`에는 최소한 두 값이 필요합니다.

```sh
GITHUB_TOKEN=github_pat_xxx
DATABASE_URL=postgresql://user:password@localhost:5432/pr_atlas
```

실행 명령은 다음입니다.

```sh
python3 -m pr_atlas_mvp.import_pr_to_postgres --owner python --repo cpython --pr 123456
```

이미 스키마가 준비된 DB에 저장만 하고 싶으면 다음 옵션을 씁니다.

```sh
python3 -m pr_atlas_mvp.import_pr_to_postgres --owner python --repo cpython --pr 123456 --skip-schema
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
        D3["REST files and patch 수집"]
        D4["ImportBatch 정규화"]
        D5["patch hunk 파싱"]
        D6["PostgreSQL schema 생성"]
        D7["PostgreSQL INSERT/UPSERT"]
    end

    subgraph NotYet["아직 구현 안 됨"]
        N1["여러 PR batch import"]
        N2["GraphQL changedFiles pagination 완료 처리"]
        N3["PR pair risk scoring"]
        N4["semantic analysis"]
        N5["UI 시각화"]
    end
```

현재 구현은 Repository Import의 최소 단위입니다.

```text
PR 하나를 가져와 충돌 분석에 필요한 파일, hunk, 원본 payload를
PostgreSQL에 저장하는 것까지 수행한다.
```
