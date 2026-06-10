from __future__ import annotations

import json
import textwrap
from dataclasses import asdict

from pr_atlas_mvp.parsing.db_plan import build_db_rows
from pr_atlas_mvp.parsing.models import ImportBatch


def print_section(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_summary(batch: ImportBatch) -> None:
    pr = batch.pull_request
    print_section("1) 가져오기 요약")
    print(f"저장소     : {batch.repository['owner']}/{batch.repository['name']}")
    print(f"PR         : #{pr.number} {pr.title}")
    print(f"상태       : {pr.state}")
    print(f"Base/Head  : {pr.base_ref} <- {pr.head_ref}")
    print(f"Head SHA   : {pr.head_sha}")
    print(f"라벨       : {', '.join(pr.labels) if pr.labels else '(없음)'}")
    print(f"파일 수    : {len(pr.files)}")
    print(f"Hunk 수    : {sum(len(file.hunks) for file in pr.files)}")


def print_normalized_json_preview(batch: ImportBatch, max_lines: int) -> None:
    print_section("2) 정규화된 JSON 미리보기")
    preview_json = json.dumps(asdict(batch), indent=2, ensure_ascii=False)
    lines = preview_json.splitlines()

    for line in lines[:max_lines]:
        print(line)

    if len(lines) > max_lines:
        print(f"... (JSON {len(lines) - max_lines}줄 생략)")


def print_db_plan(batch: ImportBatch) -> None:
    rows = build_db_rows(batch)
    print_section("3) PostgreSQL 저장 계획")
    print(
        textwrap.dedent(
            """
            이 스크립트는 아직 PostgreSQL에 직접 연결하지 않습니다.
            MVP 실험 단계에서는 나중에 UPSERT할 row 모양을 출력합니다.

            테이블 역할:
              - repositories    : GitHub 저장소당 한 row
              - pull_requests   : 정규화된 PR 메타데이터
              - file_paths      : 디렉토리 검색용 path + LTREE path_tree
              - pr_files        : PR에서 변경된 파일당 한 row
              - pr_file_hunks   : REST patch 문자열에서 파싱한 라인 범위
              - raw_payloads    : GraphQL/REST 원본 응답을 보관하는 JSONB 저장소
            """
        ).strip()
    )

    for table, table_rows in rows.items():
        print(f"\n[{table}] {len(table_rows)}개 row")
        for row in table_rows[:5]:
            print(json.dumps(row, indent=2, ensure_ascii=False))
        if len(table_rows) > 5:
            print(f"... {len(table_rows) - 5}개 row 생략")


def print_example_queries() -> None:
    print_section("4) PostgreSQL 예시 쿼리")
    print(
        textwrap.dedent(
            """
            -- LTREE로 특정 디렉토리 아래 파일 찾기:
            SELECT *
            FROM file_paths
            WHERE path_tree <@ 'src.api'::ltree;

            -- 특정 PR 파일의 hunk 라인 범위 조회:
            SELECT pf.path, h.old_start, h.old_lines, h.new_start, h.new_lines
            FROM pr_files pf
            JOIN pr_file_hunks h ON h.pr_file_id = pf.id
            WHERE pf.pull_request_id = $1
            ORDER BY pf.path, h.new_start;

            -- 이후 충돌 후보는 같은 파일과 겹치는 hunk 범위에서 계산:
            SELECT a.pull_request_id AS source_pr_id,
                   b.pull_request_id AS target_pr_id,
                   a.path,
                   ah.new_start AS source_start,
                   bh.new_start AS target_start
            FROM pr_files a
            JOIN pr_files b ON a.path = b.path
            JOIN pr_file_hunks ah ON ah.pr_file_id = a.id
            JOIN pr_file_hunks bh ON bh.pr_file_id = b.id
            WHERE a.pull_request_id < b.pull_request_id
              AND int4range(ah.new_start, ah.new_start + ah.new_lines, '[]')
                  && int4range(bh.new_start, bh.new_start + bh.new_lines, '[]');
            """
        ).strip()
    )
