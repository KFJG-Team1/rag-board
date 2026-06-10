"""Search structured note sections with pgvector similarity."""

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector.psycopg import Vector, register_vector

from learniverse.database_config import (
    MissingDatabaseURLError,
    load_database_url,
)
from learniverse.embeddings import (
    EMBEDDING_MODEL,
    MissingOpenAIAPIKeyError,
    build_embeddings_client,
    embed_query,
    load_openai_api_key,
)
from learniverse.ingest_markdown import validate_embedding_dimensions


# 질문 embedding과 section embedding 사이의 거리를 계산하는 검색 SQL이다.
# `<->`는 pgvector의 distance 연산자이며, 값이 작을수록 두 벡터가 더 가깝다.
# LEFT JOIN의 하위 쿼리는 여러 keyword row를 사람이 읽기 좋은 문자열 하나로 모아준다.
SEARCH_SECTIONS_SQL = """
SELECT
    notes.title,
    notes.author,
    note_sections.heading,
    note_sections.body,
    COALESCE(keywords.keywords, '') AS keywords,
    section_embeddings.embedding <-> %s::vector AS distance
FROM section_embeddings
JOIN note_sections ON note_sections.id = section_embeddings.section_id
JOIN notes ON notes.id = note_sections.note_id
LEFT JOIN (
    SELECT
        section_id,
        string_agg(keyword, ', ' ORDER BY keyword_index) AS keywords
    FROM section_keywords
    GROUP BY section_id
) AS keywords ON keywords.section_id = note_sections.id
WHERE section_embeddings.model = %s
ORDER BY section_embeddings.embedding <-> %s::vector
LIMIT %s
"""


@dataclass(frozen=True)
class SectionSearchResult:
    # SQL row를 그대로 튜플로 다루지 않고, 출력에 필요한 필드 이름을 붙인 결과 모델이다.
    note_title: str
    note_author: str
    section_heading: str
    body: str
    keywords: str
    distance: float


def search_sections(
    connection: Any,
    query_vector: list[float],
    limit: int,
) -> list[SectionSearchResult]:
    # DB의 embedding 컬럼이 vector(1536)이므로 검색 벡터도 같은 차원인지 먼저 확인한다.
    # 그런 다음 pgvector adapter로 감싸 SQL parameter로 안전하게 전달한다.
    validate_embedding_dimensions(query_vector)
    vector = Vector(query_vector)
    rows = connection.execute(
        SEARCH_SECTIONS_SQL,
        (
            vector,
            EMBEDDING_MODEL,
            vector,
            limit,
        ),
    ).fetchall()

    return [
        SectionSearchResult(
            note_title=str(row[0]),
            note_author=str(row[1]),
            section_heading=str(row[2]),
            body=str(row[3]),
            keywords=str(row[4]),
            distance=float(row[5]),
        )
        for row in rows
    ]


def run_search(query: str, limit: int) -> list[SectionSearchResult]:
    # CLI에서 호출하는 검색 파이프라인이다.
    # 질문을 OpenAI embedding으로 바꾸고, DB에 연결해 가장 가까운 section들을 조회한다.
    api_key = load_openai_api_key()
    database_url = load_database_url()
    embeddings_client = build_embeddings_client(api_key)
    query_vector = embed_query(query, embeddings_client)

    with psycopg.connect(database_url) as connection:
        register_vector(connection)
        return search_sections(connection, query_vector=query_vector, limit=limit)


def body_preview(body: str, max_length: int = 180) -> str:
    # 검색 결과 전체 본문을 모두 출력하면 CLI가 읽기 어려워진다.
    # 공백을 정리하고 일정 길이까지만 보여줘서 결과를 빠르게 훑을 수 있게 한다.
    preview = re.sub(r"\s+", " ", body).strip()
    if len(preview) <= max_length:
        return preview
    return preview[: max_length - 3].rstrip() + "..."


def format_source_label(result: SectionSearchResult) -> str:
    return f"{result.note_title} (작성자: {result.note_author}) > {result.section_heading}"


def format_search_results(results: list[SectionSearchResult]) -> str:
    # 검색 결과를 사람이 읽을 수 있는 CLI 출력 문자열로 바꾼다.
    # distance는 낮을수록 질문과 section의 embedding이 더 가깝다는 의미다.
    lines = [f"Results: {len(results)}"]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. {format_source_label(result)}",
                f"   Keywords: {result.keywords}",
                f"   Distance: {result.distance:.6f}",
                f"   Preview: {body_preview(result.body)}",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Learniverse note sections.")
    parser.add_argument("query", help="Question or search text to embed and search.")
    parser.add_argument("--limit", type=int, default=3, help="Number of results to return.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        print("Error: --limit must be 1 or greater.", file=sys.stderr)
        return 1

    try:
        results = run_search(query=args.query, limit=args.limit)
    except (MissingOpenAIAPIKeyError, MissingDatabaseURLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(format_search_results(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
