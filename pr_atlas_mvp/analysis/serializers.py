from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import PurePosixPath
from typing import Any

from pr_atlas_mvp.analysis.colors import color_for_pr_index
from pr_atlas_mvp.analysis.models import RiskFileFinding, SourceContext


def serialize_outputs(
    *,
    context: SourceContext,
    risk_findings: tuple[RiskFileFinding, ...],
    errors: tuple[str, ...] = (),
    codeql_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "canvas_layout": serialize_canvas_layout(context, risk_findings),
        "pr_overlay": serialize_pr_overlay(context),
        "risk_analysis": serialize_risk_analysis(
            context,
            risk_findings,
            errors,
            codeql_metadata=codeql_metadata,
        ),
        "merge_recommendation": serialize_merge_recommendation(context, risk_findings),
        "file_details": {
            str(finding.file_path_id): serialize_file_detail(context, finding)
            for finding in risk_findings
        },
    }


def serialize_canvas_layout(
    context: SourceContext,
    risk_findings: tuple[RiskFileFinding, ...],
) -> dict[str, Any]:
    risk_by_file = {finding.file_path_id: finding for finding in risk_findings}
    unique_files = {
        change.file_path_id: change.path
        for change in context.file_changes
    }
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    role_node_ids: set[str] = set()
    file_columns = 4
    file_x_start = 120
    file_y_start = 120
    file_x_gap = 180
    file_y_gap = 90
    role_x = file_x_start + file_columns * file_x_gap + 120

    for index, (file_path_id, path) in enumerate(sorted(unique_files.items(), key=lambda item: item[1])):
        group = str(PurePosixPath(path).parent)
        if group == ".":
            group = ""
        finding = risk_by_file.get(file_path_id)
        nodes.append(
            {
                "id": f"file:{file_path_id}",
                "node_type": "file",
                "file_path_id": file_path_id,
                "path": path,
                "label": PurePosixPath(path).name,
                "group": group,
                "x": file_x_start + (index % file_columns) * file_x_gap,
                "y": file_y_start + (index // file_columns) * file_y_gap,
                "width": 150,
                "height": 34,
                "semantic_cluster": group.split("/", 1)[0] if group else "root",
                "base_style": {
                    "opacity": 1.0,
                    "label_color": "danger" if finding and finding.risk_level in {"high", "critical"} else "default",
                },
            }
        )
        if finding:
            for role in finding.affected_project_roles:
                role_node_id = f"role:{role.role_id}"
                if role_node_id not in role_node_ids:
                    role_index = len(role_node_ids)
                    role_node_ids.add(role_node_id)
                    nodes.append(
                        {
                            "id": role_node_id,
                            "node_type": "project_role",
                            "label": role.name,
                            "criticality": role.criticality,
                            "x": role_x,
                            "y": file_y_start + role_index * 78,
                            "width": 190,
                            "height": 38,
                        }
                    )
                edges.append(
                    {
                        "id": f"static:file:{file_path_id}-role:{role.role_id}",
                        "edge_type": "affects_project_role",
                        "source": f"file:{file_path_id}",
                        "target": role_node_id,
                        "weight": _role_weight(role.criticality),
                        "reason": role.match_reason,
                    }
                )

    return {
        "repository_id": context.repository_id,
        "layout_version": "temporary-v1",
        "nodes": nodes,
        "edges": edges,
    }


def serialize_pr_overlay(context: SourceContext) -> dict[str, Any]:
    colors = {
        pr.id: color_for_pr_index(index)
        for index, pr in enumerate(context.pull_requests)
    }
    hunk_count_by_file_change = Counter(hunk.pr_file_id for hunk in context.hunks)
    files_by_pr: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for change in context.file_changes:
        files_by_pr[change.pull_request_id].append(
            {
                "file_path_id": change.file_path_id,
                "node_id": f"file:{change.file_path_id}",
                "path": change.path,
                "status": change.status,
                "additions": change.additions,
                "deletions": change.deletions,
                "changes": change.changes,
                "hunk_count": hunk_count_by_file_change.get(change.id, 0),
                "patch_excerpt": _patch_excerpt(change.patch),
            }
        )

    return {
        "repository_id": context.repository_id,
        "selected_pr_ids": list(context.selected_pr_ids),
        "pull_requests": [
            {
                "pull_request_id": pr.id,
                "number": pr.number,
                "title": pr.title,
                "color": colors[pr.id],
                "files": files_by_pr.get(pr.id, []),
            }
            for pr in context.pull_requests
        ],
    }


def _patch_excerpt(patch: str | None, *, max_lines: int = 28) -> str | None:
    if not patch:
        return None
    lines = patch.splitlines()
    if len(lines) <= max_lines:
        return patch
    return "\n".join([*lines[:max_lines], "..."])


def serialize_risk_analysis(
    context: SourceContext,
    risk_findings: tuple[RiskFileFinding, ...],
    errors: tuple[str, ...],
    *,
    codeql_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts = Counter(finding.risk_level for finding in risk_findings)
    top = risk_findings[0] if risk_findings else None
    summary = (
        f"가장 위험한 파일은 {top.path}입니다(위험도 {_risk_level_label(top.risk_level)}, 점수 {top.score})."
        if top
        else "분석할 변경 파일이 없습니다."
    )
    return {
        "analysis_id": context.analysis_id,
        "repository_id": context.repository_id,
        "selected_pr_ids": list(context.selected_pr_ids),
        "summary": summary,
        "risk_counts": {
            "low": counts.get("low", 0),
            "medium": counts.get("medium", 0),
            "high": counts.get("high", 0),
            "critical": counts.get("critical", 0),
        },
        "files": [_risk_file_to_dict(finding) for finding in risk_findings],
        "errors": list(errors),
        "codeql": codeql_metadata or {},
    }


def serialize_merge_recommendation(
    context: SourceContext,
    risk_findings: tuple[RiskFileFinding, ...],
) -> dict[str, Any]:
    score_by_pr: dict[int, int] = defaultdict(int)
    number_by_id = {pr.id: pr.number for pr in context.pull_requests}
    id_by_number = {pr.number: pr.id for pr in context.pull_requests}
    for finding in risk_findings:
        for pr_number in finding.related_prs:
            pr_id = id_by_number.get(pr_number)
            if pr_id is not None:
                score_by_pr[pr_id] = max(score_by_pr[pr_id], finding.score)

    ordered_pr_ids = sorted(
        context.selected_pr_ids,
        key=lambda pr_id: score_by_pr.get(pr_id, 0),
        reverse=True,
    )
    recommended_order = []
    for index, pr_id in enumerate(ordered_pr_ids):
        after_ids = ordered_pr_ids[index + 1 :]
        recommended_order.append(
            {
                "pull_request_id": pr_id,
                "number": number_by_id[pr_id],
                "reason": f"영향 점수가 높은 PR부터 검토하세요(최대 점수 {score_by_pr.get(pr_id, 0)}).",
                "required_before": after_ids,
                "risk_if_delayed": "의존 또는 겹침 관계가 있는 PR을 미루면 오래된 동작 기준으로 리뷰될 수 있습니다.",
            }
        )

    blocking_files = [
        {
            "path": finding.path,
            "risk_level": finding.risk_level,
            "public_surface_level": finding.public_surface_level,
            "related_prs": list(finding.related_prs),
        }
        for finding in risk_findings
        if finding.risk_level in {"high", "critical"}
    ]
    recommended_actions = []
    for finding in risk_findings[:10]:
        if finding.risk_level in {"high", "critical"}:
            recommended_actions.append(
                {
                    "action": "manual_review",
                    "file_path": finding.path,
                    "reason": finding.reasons[0],
                    "confidence": "medium",
                    "evidence": [item.get("reason", "위험 근거") for item in finding.evidence[:3]]
                    or list(finding.reasons[:2]),
                }
            )
        if finding.conflict_points:
            recommended_actions.append(
                {
                    "action": "rebase_before_merge",
                    "file_path": finding.path,
                    "reason": "선택한 PR들이 겹치거나 가까운 hunk를 수정합니다.",
                    "confidence": "medium",
                    "evidence": ["결정적 hunk 겹침/근접 근거"],
                }
            )

    return {
        "recommendation_id": context.analysis_id,
        "repository_id": context.repository_id,
        "selected_pr_ids": list(context.selected_pr_ids),
        "recommended_order": recommended_order,
        "blocking_files": blocking_files,
        "recommended_actions": recommended_actions,
        "llm_summary": "LLM 보고는 비활성화되어 있으며, 이 요약은 수집된 근거만 사용한 대체 출력입니다.",
    }


def serialize_file_detail(context: SourceContext, finding: RiskFileFinding) -> dict[str, Any]:
    return {
        "analysis_id": context.analysis_id,
        "repository_id": context.repository_id,
        "file_path_id": finding.file_path_id,
        "path": finding.path,
        "risk_level": finding.risk_level,
        "score": finding.score,
        "public_surface_level": finding.public_surface_level,
        "related_prs": list(finding.related_prs),
        "conflict_points": list(finding.conflict_points),
        "static_explanation": {
            "source": "codeql",
            "impact_paths": list(finding.static_impact_paths),
            "affected_roles": [role.role_id for role in finding.affected_project_roles],
            "uncertainty_signals": list(finding.uncertainty_signals),
        },
        "project_explanation": {
            "affected_project_roles": [
                {
                    "role_id": role.role_id,
                    "name": role.name,
                    "criticality": role.criticality,
                    "match_reason": role.match_reason,
                }
                for role in finding.affected_project_roles
            ]
        },
        "validation_explanation": {
            "signals": [asdict(signal) for signal in finding.validation_signals]
        },
        "rag_explanation": {
            "summary": "RAG 문서는 보조 맥락이며, 의존성 판단의 기준은 CodeQL 근거입니다.",
            "supporting_documents": [
                item.get("document_id")
                for item in finding.documentation_context
                if item.get("document_id")
            ],
        },
    }


def _risk_file_to_dict(finding: RiskFileFinding) -> dict[str, Any]:
    return {
        "file_path_id": finding.file_path_id,
        "path": finding.path,
        "node_id": finding.node_id,
        "risk_level": finding.risk_level,
        "score": finding.score,
        "public_surface_level": finding.public_surface_level,
        "change_intent": finding.change_intent,
        "related_prs": list(finding.related_prs),
        "reasons": list(finding.reasons),
        "evidence": list(finding.evidence),
        "static_impact_paths": list(finding.static_impact_paths),
        "affected_project_roles": [
            {
                "role_id": role.role_id,
                "name": role.name,
                "criticality": role.criticality,
                "match_reason": role.match_reason,
                "risk_tags": list(role.risk_tags),
            }
            for role in finding.affected_project_roles
        ],
        "validation_signals": [asdict(signal) for signal in finding.validation_signals],
        "documentation_context": list(finding.documentation_context),
        "uncertainty_signals": list(finding.uncertainty_signals),
        "codeql_queries": list(finding.codeql_queries),
    }


def _role_weight(criticality: str) -> float:
    return {
        "core": 1.0,
        "important": 0.75,
        "internal": 0.5,
        "low": 0.25,
    }.get(criticality, 0.25)


def _risk_level_label(risk_level: str) -> str:
    return {
        "low": "낮음",
        "medium": "보통",
        "high": "높음",
        "critical": "치명적",
    }.get(risk_level, risk_level)
