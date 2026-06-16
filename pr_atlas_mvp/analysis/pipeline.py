from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from pr_atlas_mvp.analysis.codeql_runner import load_or_run_codeql_analysis
from pr_atlas_mvp.analysis.context import build_rag_documents, load_source_context
from pr_atlas_mvp.analysis.deterministic import compute_deterministic_risk
from pr_atlas_mvp.analysis.langchain_adapters import (
    generate_intent_and_explanations,
    rag_documents_to_langchain,
)
from pr_atlas_mvp.analysis.models import (
    AnalysisRequest,
    AnalysisState,
    CodeQLEvidence,
    DeterministicFileRisk,
    ProjectRoleMap,
    RagDocument,
    RiskFileFinding,
    SourceContext,
    ValidationSignal,
)
from pr_atlas_mvp.analysis.progress import emit_progress
from pr_atlas_mvp.analysis.role_map import load_project_role_map
from pr_atlas_mvp.analysis.scoring import score_project_impact
from pr_atlas_mvp.analysis.serializers import serialize_outputs
from pr_atlas_mvp.analysis.storage import (
    replace_static_evidence,
    upsert_static_analysis_snapshot,
)
from pr_atlas_mvp.analysis.validation import collect_validation_signals
from pr_atlas_mvp.postgres.schema import ensure_schema


class AnalysisGraphState(TypedDict):
    session: Session
    request: AnalysisRequest
    source_context: SourceContext
    rag_documents: tuple[RagDocument, ...]
    langchain_documents: tuple[Any, ...]
    role_map: ProjectRoleMap
    codeql_evidence: CodeQLEvidence
    validation_signals: tuple[ValidationSignal, ...]
    deterministic_findings: tuple[DeterministicFileRisk, ...]
    risk_findings: tuple[RiskFileFinding, ...]
    llm_analysis: dict[str, Any]
    outputs: dict[str, Any]
    errors: tuple[str, ...]


class AnalysisGraphUpdate(TypedDict, total=False):
    source_context: SourceContext
    rag_documents: tuple[RagDocument, ...]
    langchain_documents: tuple[Any, ...]
    role_map: ProjectRoleMap
    codeql_evidence: CodeQLEvidence
    validation_signals: tuple[ValidationSignal, ...]
    deterministic_findings: tuple[DeterministicFileRisk, ...]
    risk_findings: tuple[RiskFileFinding, ...]
    llm_analysis: dict[str, Any]
    outputs: dict[str, Any]
    errors: tuple[str, ...]


def run_analysis(session: Session, request: AnalysisRequest) -> AnalysisState:
    state = cast(
        AnalysisGraphState,
        _analysis_graph().invoke({"session": session, "request": request}),
    )
    return AnalysisState(
        request=request,
        source_context=state["source_context"],
        rag_documents=state["rag_documents"],
        langchain_documents=state["langchain_documents"],
        codeql_evidence=state["codeql_evidence"],
        role_map=state["role_map"],
        validation_signals=state["validation_signals"],
        deterministic_findings=state["deterministic_findings"],
        risk_findings=state["risk_findings"],
        llm_analysis=state["llm_analysis"],
        outputs=state["outputs"],
        errors=state["errors"],
    )


@lru_cache(maxsize=1)
def _analysis_graph() -> Any:
    graph = StateGraph(AnalysisGraphState)
    graph.add_node("load_source_context", _load_source_context_node)
    graph.add_node("build_rag_documents", _build_rag_documents_node)
    graph.add_node("load_project_role_map", _load_project_role_map_node)
    graph.add_node("load_or_run_codeql_analysis", _load_or_run_codeql_analysis_node)
    graph.add_node("persist_static_evidence", _persist_static_evidence_node)
    graph.add_node("collect_validation_signals", _collect_validation_signals_node)
    graph.add_node("compute_deterministic_risk", _compute_deterministic_risk_node)
    graph.add_node("score_project_impact", _score_project_impact_node)
    graph.add_node("generate_intent_and_explanations", _generate_intent_node)
    graph.add_node("serialize_outputs", _serialize_outputs_node)

    graph.add_edge(START, "load_source_context")
    graph.add_edge("load_source_context", "build_rag_documents")
    graph.add_edge("build_rag_documents", "load_project_role_map")
    graph.add_edge("load_project_role_map", "load_or_run_codeql_analysis")
    graph.add_edge("load_or_run_codeql_analysis", "persist_static_evidence")
    graph.add_edge("persist_static_evidence", "collect_validation_signals")
    graph.add_edge("collect_validation_signals", "compute_deterministic_risk")
    graph.add_edge("compute_deterministic_risk", "score_project_impact")
    graph.add_edge("score_project_impact", "generate_intent_and_explanations")
    graph.add_edge("generate_intent_and_explanations", "serialize_outputs")
    graph.add_edge("serialize_outputs", END)
    return graph.compile()


def _load_source_context_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("load_source_context", "선택한 PR 원천 데이터를 불러옵니다.", percent=5)
    session = state["session"]
    request = state["request"]
    if request.create_schema:
        ensure_schema(session)

    context = load_source_context(
        session,
        owner=request.owner,
        repo=request.repo,
        pr_numbers=request.pr_numbers,
    )
    emit_progress("load_source_context", "선택한 PR 원천 데이터 로드가 완료되었습니다.", percent=10, status="succeeded")
    return {"source_context": context}


def _build_rag_documents_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("build_rag_documents", "RAG 문서 경계를 구성합니다.", percent=14)
    documents = build_rag_documents(state["source_context"])
    emit_progress("build_rag_documents", "RAG 문서 구성이 완료되었습니다.", percent=18, status="succeeded")
    return {
        "rag_documents": documents,
        "langchain_documents": rag_documents_to_langchain(documents),
    }


def _load_project_role_map_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("load_project_role_map", "프로젝트 역할 맵을 불러옵니다.", percent=22)
    return {"role_map": load_project_role_map(state["request"].project_role_map)}


def _load_or_run_codeql_analysis_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("load_or_run_codeql_analysis", "CodeQL 정적 분석 근거를 준비합니다.", percent=28)
    return {
        "codeql_evidence": load_or_run_codeql_analysis(
            state["request"],
            state["source_context"],
        )
    }


def _persist_static_evidence_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("persist_static_evidence", "정적 분석 근거 snapshot을 저장합니다.", percent=70)
    session = state["session"]
    context = state["source_context"]
    codeql_evidence = state["codeql_evidence"]
    with session.begin_nested():
        snapshot_row = upsert_static_analysis_snapshot(session, codeql_evidence.snapshot)
        codeql_evidence = CodeQLEvidence(
            snapshot=replace(codeql_evidence.snapshot, id=snapshot_row.id),
            changes=codeql_evidence.changes,
            findings=codeql_evidence.findings,
            errors=codeql_evidence.errors,
        )
        replace_static_evidence(
            session,
            snapshot_id=snapshot_row.id,
            pull_request_ids=context.selected_pr_ids,
            changes=codeql_evidence.changes,
            findings=codeql_evidence.findings,
        )

    emit_progress("persist_static_evidence", "정적 분석 근거 저장이 완료되었습니다.", percent=74, status="succeeded")
    return {"codeql_evidence": codeql_evidence}


def _collect_validation_signals_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("collect_validation_signals", "검증 신호를 수집합니다.", percent=78)
    return {
        "validation_signals": collect_validation_signals(
            context=state["source_context"],
            codeql_evidence=state["codeql_evidence"],
            repo_root=state["request"].repo_root,
            validation_evidence=state["request"].validation_evidence,
        )
    }


def _compute_deterministic_risk_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("compute_deterministic_risk", "파일 겹침과 근접 hunk 위험을 계산합니다.", percent=82)
    return {
        "deterministic_findings": compute_deterministic_risk(
            state["source_context"]
        )
    }


def _score_project_impact_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("score_project_impact", "CodeQL/역할 맵 기반 영향 점수를 계산합니다.", percent=86)
    return {
        "risk_findings": score_project_impact(
            context=state["source_context"],
            deterministic_findings=state["deterministic_findings"],
            codeql_evidence=state["codeql_evidence"],
            role_map=state["role_map"],
            validation_signals=state["validation_signals"],
        )
    }


def _generate_intent_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("generate_intent_and_explanations", "LLM 설명/의도 생성 단계를 준비합니다.", percent=90)
    return {
        "llm_analysis": generate_intent_and_explanations(
            risk_findings=state["risk_findings"],
            langchain_documents=state["langchain_documents"],
            use_llm=state["request"].use_llm,
            model=state["request"].llm_model,
            timeout_seconds=state["request"].llm_timeout_seconds,
        )
    }


def _serialize_outputs_node(state: AnalysisGraphState) -> AnalysisGraphUpdate:
    emit_progress("serialize_outputs", "프런트엔드 응답 JSON을 구성합니다.", percent=98)
    errors = tuple(state["codeql_evidence"].errors)
    outputs = serialize_outputs(
        context=state["source_context"],
        risk_findings=state["risk_findings"],
        errors=errors,
        codeql_metadata={
            "query_profile": state["codeql_evidence"].snapshot.metadata.get(
                "codeql_query_profile",
                state["request"].codeql_query_profile,
            ),
            "query_suite": state["codeql_evidence"].snapshot.metadata.get("query_suite"),
            "snapshot_status": state["codeql_evidence"].snapshot.status,
            "label": (
                "빠른 CodeQL-lite 분석 결과"
                if state["request"].codeql_query_profile == "lite"
                else "정밀 CodeQL-full 분석 결과"
            ),
        },
    )
    llm_summary = state["llm_analysis"].get("summary")
    if isinstance(llm_summary, str) and llm_summary:
        outputs["merge_recommendation"]["llm_summary"] = llm_summary
    outputs["llm_analysis"] = state["llm_analysis"]
    emit_progress("serialize_outputs", "분석 응답 생성이 완료되었습니다.", percent=100, status="succeeded")
    return {
        "outputs": outputs,
        "errors": errors,
    }
