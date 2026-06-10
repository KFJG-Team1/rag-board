"""Answer questions from section search results."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from learniverse.database_config import MissingDatabaseURLError
from learniverse.embeddings import MissingOpenAIAPIKeyError, load_openai_api_key
from learniverse.search_sections import SectionSearchResult, format_source_label, run_search


# 기본 답변 모델이다.
# 로컬 학습에서는 비용과 지연시간 부담이 작은 mini 모델을 기본값으로 두고,
# 실제 모델 교체는 `.env`의 OPENAI_CHAT_MODEL로 배울 수 있게 한다.
DEFAULT_CHAT_MODEL = "gpt-5.4-mini"

RAG_SYSTEM_PROMPT = """너는 Learniverse 학습 노트 RAG 도우미다.
제공된 context 안의 정보만 사용해 한국어로 답한다.
context에서 확인할 수 없는 내용은 모른다고 말한다.
답변 끝에는 사용한 출처 번호를 [1], [2] 형식으로 짧게 표시한다."""


@dataclass(frozen=True)
class AnswerQuestionResult:
    # CLI 출력에 필요한 최소 결과 모델이다.
    # answer는 LLM이 만든 답변이고, sources는 답변에 사용하라고 전달한 검색 section들이다.
    question: str
    answer: str
    sources: list[SectionSearchResult]
    model: str


def load_openai_chat_model(env_file: str | Path = ".env") -> str:
    """Load OPENAI_CHAT_MODEL from .env, falling back to the default chat model."""
    load_dotenv(dotenv_path=env_file)
    model = os.getenv("OPENAI_CHAT_MODEL", "").strip()
    return model or DEFAULT_CHAT_MODEL


def build_chat_model(api_key: str, model: str) -> ChatOpenAI:
    # LangChain의 ChatOpenAI client를 만드는 얇은 helper다.
    # temperature 같은 세부 튜닝은 이번 단계의 핵심이 아니므로 모델과 키만 명시한다.
    return ChatOpenAI(model=model, api_key=api_key)


def build_rag_context(sources: list[SectionSearchResult]) -> str:
    # 검색된 section들을 LLM이 읽기 쉬운 context 블록으로 바꾼다.
    # 번호를 붙여 두면 답변 끝의 출처 표기가 실제 검색 결과와 연결된다.
    blocks = []
    for index, source in enumerate(sources, start=1):
        keywords = source.keywords or "없음"
        blocks.append(
            f"[{index}]\n"
            f"문서 제목: {source.note_title}\n"
            f"소제목: {source.section_heading}\n"
            f"키워드: {keywords}\n"
            "본문:\n"
            f"{source.body}"
        )
    return "\n\n---\n\n".join(blocks)


def build_user_prompt(question: str, context: str) -> str:
    return (
        "아래 context를 바탕으로 질문에 답해줘.\n\n"
        f"질문:\n{question}\n\n"
        f"context:\n{context}"
    )


def message_content_to_text(content: Any) -> str:
    # LangChain message content는 보통 문자열이지만, 모델/SDK에 따라 block list가 올 수도 있다.
    # CLI는 최종 텍스트만 필요하므로 문자열 block만 안전하게 이어 붙인다.
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return str(content).strip()


def generate_answer(
    question: str,
    sources: list[SectionSearchResult],
    chat_model: Any,
) -> str:
    if not sources:
        return "검색된 section이 없어 답변을 만들 수 없습니다. 먼저 ingestion을 실행했는지 확인해 주세요."

    context = build_rag_context(sources)
    response = chat_model.invoke(
        [
            ("system", RAG_SYSTEM_PROMPT),
            ("human", build_user_prompt(question, context)),
        ]
    )
    return message_content_to_text(response.content)


def answer_question(question: str, limit: int) -> AnswerQuestionResult:
    # 최소 RAG 파이프라인이다.
    # 1) 질문과 가까운 section을 vector search로 찾고 2) 그 section들을 context로 LLM 답변을 만든다.
    api_key = load_openai_api_key()
    model = load_openai_chat_model()
    sources = run_search(question, limit=limit)
    chat_model = build_chat_model(api_key=api_key, model=model)
    answer = generate_answer(question=question, sources=sources, chat_model=chat_model)

    return AnswerQuestionResult(
        question=question,
        answer=answer,
        sources=sources,
        model=model,
    )


def format_answer_result(result: AnswerQuestionResult) -> str:
    lines = [
        f"Question: {result.question}",
        f"Model: {result.model}",
        "",
        "Answer:",
        result.answer,
        "",
        "Sources:",
    ]

    if not result.sources:
        lines.append("- No section search results.")
        return "\n".join(lines)

    for index, source in enumerate(result.sources, start=1):
        lines.append(
            f"[{index}] {format_source_label(source)} (distance: {source.distance:.6f})"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Answer a question using section RAG.")
    parser.add_argument("question", help="Question to answer from stored note sections.")
    parser.add_argument("--limit", type=int, default=3, help="Number of sections to use.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        print("Error: --limit must be 1 or greater.", file=sys.stderr)
        return 1

    try:
        result = answer_question(question=args.question, limit=args.limit)
    except (MissingOpenAIAPIKeyError, MissingDatabaseURLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(format_answer_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
