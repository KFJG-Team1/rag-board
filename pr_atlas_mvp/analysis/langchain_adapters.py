from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, ConfigDict, Field

from pr_atlas_mvp.analysis.models import RagDocument, RiskFileFinding
from pr_atlas_mvp.analysis.progress import emit_progress


FALLBACK_LLM_SUMMARY = (
    "LLM 보고는 비활성화되어 있으며, 이 요약은 수집된 근거만 사용한 대체 출력입니다."
)


class EvidenceBoundFileExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path_id: int | None
    file_path: str
    explanation: str
    review_focus: list[str]


class EvidenceBoundReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_intent: str = Field(description="선택한 PR 변경의 전체 의도")
    review_focus: list[str] = Field(description="리뷰어가 확인할 핵심 항목")
    summary: str = Field(description="한국어 분석 요약")
    file_explanations: list[EvidenceBoundFileExplanation] = Field(
        description="파일별 설명. 위험 점수나 risk_level을 재판단하지 않는다."
    )
    merge_notes: list[str] = Field(description="병합 전 확인할 보조 메모")


EVIDENCE_REPORT_PARSER = PydanticOutputParser(pydantic_object=EvidenceBoundReport)


def rag_documents_to_langchain(
    documents: tuple[RagDocument, ...],
) -> tuple[Document, ...]:
    return tuple(
        Document(
            page_content=document.content,
            metadata={
                **document.metadata,
                "document_id": document.document_id,
                "document_type": document.document_type,
                "repository_id": document.repository_id,
                "pull_request_id": document.pull_request_id,
                "file_path_id": document.file_path_id,
                "path": document.path,
                "title": document.title,
            },
        )
        for document in documents
    )


def generate_intent_and_explanations(
    *,
    risk_findings: tuple[RiskFileFinding, ...],
    langchain_documents: tuple[Document, ...],
    use_llm: bool,
    model: str = "gpt-5.5",
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    if not use_llm:
        return {
            "enabled": False,
            "summary": FALLBACK_LLM_SUMMARY,
            "reports": [],
            "document_count": len(langchain_documents),
        }

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "enabled": False,
            "summary": FALLBACK_LLM_SUMMARY,
            "reports": [],
            "document_count": len(langchain_documents),
            "errors": ["OPENAI_API_KEY가 설정되지 않았습니다."],
            "format_instructions": EVIDENCE_REPORT_PARSER.get_format_instructions(),
            "top_files": [finding.path for finding in risk_findings[:5]],
        }

    packet = _build_evidence_packet(risk_findings, langchain_documents)
    emit_progress("openai_llm", "OpenAI LLM 설명 생성을 시작합니다.", percent=92)
    try:
        response = _create_openai_response(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            evidence_packet=packet,
        )
        report = EvidenceBoundReport.model_validate_json(_extract_response_text(response))
    except Exception as exc:  # noqa: BLE001
        emit_progress(
            "openai_llm",
            "OpenAI LLM 설명 생성이 실패해 deterministic 요약을 유지합니다.",
            percent=94,
            status="failed",
        )
        return {
            "enabled": True,
            "model": model,
            "summary": FALLBACK_LLM_SUMMARY,
            "reports": [],
            "document_count": len(langchain_documents),
            "errors": [f"OpenAI LLM 호출 실패: {exc}"],
            "top_files": [finding.path for finding in risk_findings[:5]],
        }

    emit_progress("openai_llm", "OpenAI LLM 설명 생성이 완료되었습니다.", percent=96, status="succeeded")
    return {
        "enabled": True,
        "model": model,
        "summary": report.summary,
        "report": report.model_dump(),
        "reports": [report.model_dump()],
        "document_count": len(langchain_documents),
        "errors": [],
        "top_files": [finding.path for finding in risk_findings[:5]],
    }


def _create_openai_response(
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
    evidence_packet: dict[str, Any],
) -> Any:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=timeout_seconds)
    return client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "당신은 PR 영향 분석 설명을 작성한다. "
                            "risk_level, score, CodeQL evidence, hunk conflict는 절대 새로 만들거나 낮추지 말고 "
                            "제공된 evidence packet에 근거한 한국어 설명과 리뷰 포커스만 작성한다."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(evidence_packet, ensure_ascii=False),
                    }
                ],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "evidence_bound_pr_report",
                "schema": EvidenceBoundReport.model_json_schema(),
                "strict": True,
            }
        },
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    if isinstance(response, dict):
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text
        output = response.get("output")
    else:
        output = getattr(response, "output", None)

    parts: list[str] = []
    for item in output or []:
        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
        for content_item in content or []:
            if isinstance(content_item, dict):
                text = content_item.get("text")
            else:
                text = getattr(content_item, "text", None)
            if isinstance(text, str):
                parts.append(text)
    text = "".join(parts).strip()
    if not text:
        raise ValueError("OpenAI 응답에서 JSON text를 찾지 못했습니다.")
    return text


def _build_evidence_packet(
    risk_findings: tuple[RiskFileFinding, ...],
    langchain_documents: tuple[Document, ...],
) -> dict[str, Any]:
    return {
        "instruction": (
            "설명/의도/리뷰 포커스만 생성한다. risk_level, score, CodeQL evidence, hunk conflict를 변경하지 않는다."
        ),
        "risk_files": [_finding_packet(finding) for finding in risk_findings[:8]],
        "documents": [_document_packet(document) for document in langchain_documents[:12]],
    }


def _finding_packet(finding: RiskFileFinding) -> dict[str, Any]:
    return {
        "file_path_id": finding.file_path_id,
        "path": finding.path,
        "risk_level": finding.risk_level,
        "score": finding.score,
        "public_surface_level": finding.public_surface_level,
        "related_prs": list(finding.related_prs),
        "reasons": list(finding.reasons[:5]),
        "affected_project_roles": [
            {
                "role_id": role.role_id,
                "name": role.name,
                "criticality": role.criticality,
                "match_reason": role.match_reason,
            }
            for role in finding.affected_project_roles[:5]
        ],
        "codeql_queries": list(finding.codeql_queries[:5]),
        "uncertainty_signals": list(finding.uncertainty_signals[:5]),
        "conflict_points": list(finding.conflict_points[:5]),
        "evidence": [_compact_mapping(item) for item in finding.evidence[:5]],
        "static_impact_paths": [_compact_mapping(item) for item in finding.static_impact_paths[:3]],
    }


def _document_packet(document: Document) -> dict[str, Any]:
    metadata = document.metadata
    return {
        "document_id": metadata.get("document_id"),
        "document_type": metadata.get("document_type"),
        "pull_request_id": metadata.get("pull_request_id"),
        "file_path_id": metadata.get("file_path_id"),
        "path": metadata.get("path"),
        "title": metadata.get("title"),
        "content": _truncate(document.page_content, 700),
    }


def _compact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("reason", "finding_type", "query_id", "confidence", "path", "message"):
        if key in value:
            result[key] = value[key]
    if not result:
        for key, item in list(value.items())[:5]:
            result[key] = _truncate(str(item), 180)
    return result


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."
