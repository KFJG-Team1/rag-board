"""OpenAI embedding helpers for Learniverse."""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


# Learniverse에서 사용할 embedding 모델 설정을 한 곳에 모아둔다.
# DB의 `section_embeddings.embedding vector(1536)` 컬럼도 이 차원 수와 맞아야 한다.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class MissingOpenAIAPIKeyError(RuntimeError):
    """Raised when OPENAI_API_KEY is not configured."""


def load_openai_api_key(env_file: str | Path = ".env") -> str:
    """Load OPENAI_API_KEY from .env or the process environment."""
    # `.env`에 있는 값을 현재 프로세스의 환경 변수처럼 읽을 수 있게 로드한다.
    # 실제 키 값은 저장소에 커밋하지 않고, 로컬 `.env`에만 둔다.
    load_dotenv(dotenv_path=env_file)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise MissingOpenAIAPIKeyError(
            "OPENAI_API_KEY is not set. Add OPENAI_API_KEY=your_api_key to .env."
        )
    return api_key


def build_embeddings_client(api_key: str) -> OpenAIEmbeddings:
    # LangChain의 OpenAIEmbeddings client를 만드는 얇은 helper다.
    # client 생성 코드를 한 곳에 두면 ingestion과 search가 같은 모델 설정을 공유한다.
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=api_key)


def embed_documents(texts: list[str], embeddings_client: Any) -> list[list[float]]:
    # 여러 section 텍스트를 한 번에 embedding한다.
    # 입력 개수와 결과 벡터 개수가 다르면 이후 DB 저장에서 section과 vector가 어긋나므로 바로 실패시킨다.
    vectors = embeddings_client.embed_documents(texts)
    if len(vectors) != len(texts):
        raise ValueError("Embedding result count does not match text count.")
    return [list(vector) for vector in vectors]


def embed_query(text: str, embeddings_client: Any) -> list[float]:
    # 검색어는 문서 목록이 아니라 질문 하나이므로 query embedding API를 사용한다.
    # 반환된 벡터는 pgvector 거리 검색의 기준점이 된다.
    return list(embeddings_client.embed_query(text))
