"""Ingest structured Markdown notes into PostgreSQL and pgvector."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import Vector, register_vector

from learniverse.database_config import (
    MissingDatabaseURLError,
    load_database_url,
)
from learniverse.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    MissingOpenAIAPIKeyError,
    build_embeddings_client,
    embed_documents,
    load_openai_api_key,
)
from learniverse.markdown_layout import (
    DEFAULT_NOTES_DIR,
    LAYOUT_VERSION,
    MarkdownLayoutError,
    StructuredNote,
    StructuredSection,
    content_hash,
    load_structured_notes,
)


# 로컬 학습용 DB를 section 중심 구조로 다시 만들기 위한 reset SQL이다.
# DROP TABLE은 기존 데이터를 지우므로 실제 서비스에서는 migration으로 다뤄야 하지만,
# 지금은 구조를 학습하고 반복 실행하기 위한 로컬 실험 단계라 reset 방식을 사용한다.
RESET_SCHEMA_SQL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "DROP TABLE IF EXISTS section_embeddings CASCADE",
    "DROP TABLE IF EXISTS section_keywords CASCADE",
    "DROP TABLE IF EXISTS note_sections CASCADE",
    "DROP TABLE IF EXISTS notes CASCADE",
]

# 핵심 DB 모델이다.
# notes는 문서 원본, note_sections는 검색 단위, section_keywords는 section별 키워드,
# section_embeddings는 pgvector 컬럼에 저장되는 section embedding을 담당한다.
CREATE_SCHEMA_SQL = [
    """
    CREATE TABLE notes (
        id BIGSERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        source_path TEXT NOT NULL UNIQUE,
        raw_content TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        layout_version TEXT NOT NULL DEFAULT 'section-author-v1',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE note_sections (
        id BIGSERIAL PRIMARY KEY,
        note_id BIGINT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
        section_index INTEGER NOT NULL,
        heading TEXT NOT NULL,
        body TEXT NOT NULL,
        body_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (note_id, section_index)
    )
    """,
    """
    CREATE TABLE section_keywords (
        id BIGSERIAL PRIMARY KEY,
        section_id BIGINT NOT NULL REFERENCES note_sections(id) ON DELETE CASCADE,
        keyword_index INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        UNIQUE (section_id, keyword_index)
    )
    """,
    f"""
    CREATE TABLE section_embeddings (
        id BIGSERIAL PRIMARY KEY,
        section_id BIGINT NOT NULL REFERENCES note_sections(id) ON DELETE CASCADE,
        model TEXT NOT NULL,
        dimensions INTEGER NOT NULL,
        embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
        embedding_input TEXT NOT NULL,
        embedding_input_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (section_id, model)
    )
    """,
]

# 아래 INSERT SQL들은 모두 upsert 방식이다.
# 같은 source_path, 같은 section_index, 같은 keyword_index, 같은 model을 다시 저장해도
# 중복 row를 늘리지 않고 기존 row를 갱신한다.
INSERT_NOTE_SQL = """
INSERT INTO notes (title, author, source_path, raw_content, content_hash, layout_version)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (source_path) DO UPDATE SET
    title = EXCLUDED.title,
    author = EXCLUDED.author,
    raw_content = EXCLUDED.raw_content,
    content_hash = EXCLUDED.content_hash,
    layout_version = EXCLUDED.layout_version,
    updated_at = now()
RETURNING id
"""

INSERT_SECTION_SQL = """
INSERT INTO note_sections (note_id, section_index, heading, body, body_hash)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (note_id, section_index) DO UPDATE SET
    heading = EXCLUDED.heading,
    body = EXCLUDED.body,
    body_hash = EXCLUDED.body_hash,
    updated_at = now()
RETURNING id
"""

INSERT_KEYWORD_SQL = """
INSERT INTO section_keywords (section_id, keyword_index, keyword)
VALUES (%s, %s, %s)
ON CONFLICT (section_id, keyword_index) DO UPDATE SET
    keyword = EXCLUDED.keyword
"""

INSERT_SECTION_EMBEDDING_SQL = """
INSERT INTO section_embeddings (
    section_id,
    model,
    dimensions,
    embedding,
    embedding_input,
    embedding_input_hash
)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (section_id, model) DO UPDATE SET
    dimensions = EXCLUDED.dimensions,
    embedding = EXCLUDED.embedding,
    embedding_input = EXCLUDED.embedding_input,
    embedding_input_hash = EXCLUDED.embedding_input_hash,
    updated_at = now()
"""


@dataclass(frozen=True)
class SectionForEmbedding:
    # DB에 section을 먼저 저장해야 section_id를 얻을 수 있다.
    # 그 뒤 section_id와 embedding_input을 묶어 두었다가 일괄 embedding 후 다시 저장한다.
    section_id: int
    embedding_input: str


@dataclass(frozen=True)
class IngestMarkdownResult:
    # CLI 출력과 검증에서 사용할 요약 결과다.
    # 실제 저장 row를 모두 반환하지 않고, 학습자가 확인할 핵심 count만 담는다.
    note_count: int
    section_count: int
    keyword_count: int
    embedding_count: int


def reset_schema(connection: Any) -> None:
    # PostgreSQL에 vector 확장을 준비하고, 사용할 네 테이블을 새로 만든다.
    # register_vector()를 호출해야 Python의 pgvector 객체를 psycopg가 DB vector 타입으로 보낼 수 있다.
    for statement in RESET_SCHEMA_SQL:
        connection.execute(statement)
    register_vector(connection)
    for statement in CREATE_SCHEMA_SQL:
        connection.execute(statement)


def insert_note(connection: Any, note: StructuredNote) -> int:
    # StructuredNote 하나를 `notes` 테이블에 저장한다.
    # RETURNING id를 사용해 방금 insert/update된 note의 primary key를 받아 section 저장에 사용한다.
    row = connection.execute(
        INSERT_NOTE_SQL,
        (
            note.title,
            note.author,
            note.source_path,
            note.raw_content,
            content_hash(note.raw_content),
            LAYOUT_VERSION,
        ),
    ).fetchone()
    return int(row[0])


def insert_section(
    connection: Any,
    note_id: int,
    section_index: int,
    section: StructuredSection,
) -> int:
    # StructuredSection 하나를 `note_sections`에 저장한다.
    # section_index는 원문 안에서 section이 등장한 순서를 보존하고, unique key의 일부가 된다.
    row = connection.execute(
        INSERT_SECTION_SQL,
        (
            note_id,
            section_index,
            section.heading,
            section.body,
            content_hash(section.body),
        ),
    ).fetchone()
    return int(row[0])


def insert_keywords(connection: Any, section_id: int, keywords: tuple[str, ...]) -> None:
    # section의 keyword 목록을 별도 테이블에 저장한다.
    # keyword_index를 함께 저장하면 DB에서 다시 읽을 때 원래 bullet 순서를 복원할 수 있다.
    for keyword_index, keyword in enumerate(keywords):
        connection.execute(
            INSERT_KEYWORD_SQL,
            (
                section_id,
                keyword_index,
                keyword,
            ),
        )


def build_embedding_input(note: StructuredNote, section: StructuredSection) -> str:
    # embedding은 본문만 넣는 대신 문서 제목, 소제목, 키워드, 본문을 함께 넣는다.
    # 이렇게 하면 검색어가 본문 단어와 정확히 같지 않아도 구조적 맥락을 반영할 가능성이 커진다.
    return (
        f"문서 제목: {note.title}\n"
        f"소제목: {section.heading}\n"
        f"키워드: {', '.join(section.keywords)}\n"
        "본문:\n"
        f"{section.body}"
    )


def validate_embedding_dimensions(vector: list[float]) -> None:
    # DB 컬럼이 vector(1536)으로 고정되어 있으므로, 다른 길이의 벡터가 들어오면 저장 전에 막는다.
    # 모델을 바꾸면 이 상수와 DB schema를 함께 바꿔야 한다.
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions, got {len(vector)}."
        )


def insert_section_embedding(
    connection: Any,
    section_id: int,
    embedding_input: str,
    vector: list[float],
) -> None:
    # section embedding을 `section_embeddings`에 저장한다.
    # Vector(vector)는 Python list[float]를 PostgreSQL pgvector 타입으로 전달하기 위한 adapter 객체다.
    validate_embedding_dimensions(vector)
    connection.execute(
        INSERT_SECTION_EMBEDDING_SQL,
        (
            section_id,
            EMBEDDING_MODEL,
            EMBEDDING_DIMENSIONS,
            Vector(vector),
            embedding_input,
            content_hash(embedding_input),
        ),
    )


def ingest_markdown(notes_dir: str | Path = DEFAULT_NOTES_DIR) -> IngestMarkdownResult:
    # 전체 ingestion 파이프라인이다.
    # 1) 설정과 Markdown을 읽고 2) DB schema를 준비한 뒤 3) notes/sections/keywords를 저장하고
    # 4) section 단위 embedding을 생성해 pgvector 컬럼에 저장한다.
    api_key = load_openai_api_key()
    database_url = load_database_url()
    notes = load_structured_notes(notes_dir)
    embeddings_client = build_embeddings_client(api_key)

    with psycopg.connect(database_url) as connection:
        reset_schema(connection)
        sections_for_embedding: list[SectionForEmbedding] = []
        keyword_count = 0

        # 관계형 데이터를 먼저 저장한다.
        # section embedding은 section_id가 필요하므로, section row를 만든 뒤 입력 텍스트를 따로 모은다.
        for note in notes:
            note_id = insert_note(connection, note)
            for section_index, section in enumerate(note.sections):
                section_id = insert_section(connection, note_id, section_index, section)
                insert_keywords(connection, section_id, section.keywords)
                keyword_count += len(section.keywords)
                sections_for_embedding.append(
                    SectionForEmbedding(
                        section_id=section_id,
                        embedding_input=build_embedding_input(note, section),
                    )
                )

        # OpenAI embedding API는 section별 입력 텍스트 목록을 한 번에 보낸다.
        # 결과 벡터는 같은 순서로 돌아온다고 보고, 앞에서 모아둔 section_id와 다시 짝지어 저장한다.
        embedding_inputs = [section.embedding_input for section in sections_for_embedding]
        vectors = embed_documents(embedding_inputs, embeddings_client)

        for section, vector in zip(sections_for_embedding, vectors):
            insert_section_embedding(
                connection,
                section_id=section.section_id,
                embedding_input=section.embedding_input,
                vector=vector,
            )

    return IngestMarkdownResult(
        note_count=len(notes),
        section_count=len(sections_for_embedding),
        keyword_count=keyword_count,
        embedding_count=len(sections_for_embedding),
    )


def format_ingest_summary(result: IngestMarkdownResult) -> str:
    return (
        f"Stored notes: {result.note_count}\n"
        f"Stored sections: {result.section_count}\n"
        f"Stored keywords: {result.keyword_count}\n"
        f"Stored section embeddings: {result.embedding_count}"
    )


def main() -> int:
    try:
        result = ingest_markdown()
    except (MissingOpenAIAPIKeyError, MissingDatabaseURLError, MarkdownLayoutError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(format_ingest_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
