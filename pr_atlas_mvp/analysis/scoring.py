from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

from pr_atlas_mvp.analysis.deterministic import classify_path
from pr_atlas_mvp.analysis.models import (
    CodeQLEvidence,
    DeterministicFileRisk,
    FileChangeInfo,
    ProjectRoleMap,
    RiskFileFinding,
    RoleMatch,
    SourceContext,
    StaticImpactFindingInput,
    ValidationSignal,
)
from pr_atlas_mvp.analysis.role_map import highest_criticality, match_roles_for_file


CRITICALITY_SCORE = {"core": 25, "important": 15, "internal": 6, "low": 0}


def score_project_impact(
    *,
    context: SourceContext,
    deterministic_findings: tuple[DeterministicFileRisk, ...],
    codeql_evidence: CodeQLEvidence,
    role_map: ProjectRoleMap,
    validation_signals: tuple[ValidationSignal, ...],
) -> tuple[RiskFileFinding, ...]:
    changes_by_file = _changes_by_file(context.file_changes)
    static_by_file = _static_findings_by_file(codeql_evidence.findings)
    symbols_by_file = _symbols_by_file(codeql_evidence)
    validation_by_file = _validation_by_file(context, validation_signals, symbols_by_file)
    deterministic_by_file = {
        finding.file_path_id: finding for finding in deterministic_findings
    }

    risk_findings: list[RiskFileFinding] = []
    for file_path_id, changes in sorted(
        changes_by_file.items(), key=lambda item: item[1][0].path
    ):
        deterministic = deterministic_by_file.get(file_path_id)
        path = changes[0].path
        static_findings = tuple(static_by_file.get(file_path_id, []))
        symbol_names = tuple(sorted(symbols_by_file.get(file_path_id, set())))
        roles = match_roles_for_file(
            path,
            role_map=role_map,
            static_findings=static_findings,
            symbol_names=symbol_names,
        )
        validation = tuple(validation_by_file.get(file_path_id, []))

        score = deterministic.score if deterministic else 0
        reasons = list(deterministic.reasons if deterministic else ())
        evidence: list[dict[str, object]] = []
        uncertainty: list[str] = []
        codeql_queries: set[str] = set()

        static_score, static_reasons, static_evidence, static_queries = _score_static_findings(static_findings)
        score += static_score
        reasons.extend(static_reasons)
        evidence.extend(static_evidence)
        codeql_queries.update(static_queries)

        role_score, role_reasons = _score_roles(roles)
        score += role_score
        reasons.extend(role_reasons)

        public_score, public_reasons = _score_public_surface(static_findings, roles, validation)
        score += public_score
        reasons.extend(public_reasons)

        change_score, change_reasons = _score_change_risk(changes)
        score += change_score
        reasons.extend(change_reasons)

        verification_delta, verification_reasons = _score_validation(validation)
        score += verification_delta
        reasons.extend(verification_reasons)

        if codeql_evidence.snapshot.status == "partial":
            score += 8
            uncertainty.append("CodeQL 스냅샷이 부분 결과입니다.")
        elif codeql_evidence.snapshot.status == "failed":
            score += 8
            uncertainty.append("CodeQL 정적 영향 분석을 사용할 수 없어 결정적 대체 분석을 사용했습니다.")

        if not static_findings and _looks_like_code(path):
            score += 6
            uncertainty.append("변경된 코드 파일에 매핑된 CodeQL 정적 영향 결과가 없습니다.")
        if role_map.is_default:
            uncertainty.append("project-role-map.yaml이 없어 기본 경로 역할을 사용했습니다.")
        if _needs_validation(roles, static_findings) and not validation:
            score += 5
            uncertainty.append("핵심/공개 영향에 대한 검증 근거가 없습니다.")

        categories = classify_path(path)
        if set(categories).issubset({"docs"}) and not _has_hard_static(static_findings, roles):
            score = min(score, 24)
        elif set(categories).issubset({"test"}) and not _has_hard_static(static_findings, roles):
            score = min(score, 35)

        public_surface_level = _public_surface_level(static_findings, roles, categories)
        risk_findings.append(
            RiskFileFinding(
                file_path_id=file_path_id,
                path=path,
                node_id=f"file:{file_path_id}",
                score=max(score, 0),
                risk_level=risk_level(max(score, 0)),
                public_surface_level=public_surface_level,
                related_prs=tuple(sorted({change.pr_number for change in changes})),
                reasons=tuple(dict.fromkeys(reasons)) or ("강한 위험 신호가 발견되지 않았습니다.",),
                evidence=tuple(evidence),
                static_impact_paths=tuple(_static_paths(static_findings)),
                affected_project_roles=roles,
                validation_signals=validation,
                documentation_context=tuple(_documentation_context(validation)),
                uncertainty_signals=tuple(dict.fromkeys(uncertainty)),
                codeql_queries=tuple(sorted(codeql_queries)),
                conflict_points=deterministic.conflict_points if deterministic else (),
                change_intent="unknown",
            )
        )

    return tuple(sorted(risk_findings, key=lambda item: item.score, reverse=True))


def risk_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _changes_by_file(file_changes: tuple[FileChangeInfo, ...]) -> dict[int, list[FileChangeInfo]]:
    grouped: dict[int, list[FileChangeInfo]] = defaultdict(list)
    for change in file_changes:
        grouped[change.file_path_id].append(change)
    return grouped


def _static_findings_by_file(
    findings: tuple[StaticImpactFindingInput, ...],
) -> dict[int, list[StaticImpactFindingInput]]:
    grouped: dict[int, list[StaticImpactFindingInput]] = defaultdict(list)
    for finding in findings:
        grouped[finding.file_path_id].append(finding)
    return grouped


def _symbols_by_file(codeql_evidence: CodeQLEvidence) -> dict[int, set[str]]:
    grouped: dict[int, set[str]] = defaultdict(set)
    for change in codeql_evidence.changes:
        grouped[change.file_path_id].add(change.symbol_name)
    return grouped


def _validation_by_file(
    context: SourceContext,
    signals: tuple[ValidationSignal, ...],
    symbols_by_file: dict[int, set[str]],
) -> dict[int, list[ValidationSignal]]:
    grouped: dict[int, list[ValidationSignal]] = defaultdict(list)
    paths_by_file = {change.file_path_id: change.path for change in context.file_changes}
    for file_path_id, path in paths_by_file.items():
        symbols = symbols_by_file.get(file_path_id, set())
        for signal in signals:
            values = [signal.target, signal.source or "", signal.document_id or ""]
            if path in values or any(symbol and symbol in " ".join(values) for symbol in symbols):
                grouped[file_path_id].append(signal)
    return grouped


def _score_static_findings(
    findings: tuple[StaticImpactFindingInput, ...],
) -> tuple[int, list[str], list[dict[str, object]], set[str]]:
    score = 0
    reasons: list[str] = []
    evidence: list[dict[str, object]] = []
    queries: set[str] = set()
    reverse_affected_files = 0

    for finding in findings:
        queries.add(f"{finding.query_id}@{finding.query_version}")
        if finding.confidence < 0.5:
            reasons.append(f"신뢰도가 낮은 CodeQL {finding.finding_type} 결과를 불확실성으로 유지했습니다.")
            continue
        if finding.finding_type == "public_surface":
            score += 12
            reasons.append("CodeQL이 공개 표면 영향을 찾았습니다.")
        elif finding.finding_type == "reverse_dependency":
            reverse_affected_files += max(1, len(finding.affected_paths))
            reasons.append("CodeQL이 역방향 의존성 영향을 찾았습니다.")
        elif finding.finding_type in {"data_flow", "control_flow"}:
            score += 15
            reasons.append(f"CodeQL이 {finding.finding_type.replace('_', '-')} 영향을 찾았습니다.")
        elif finding.finding_type == "test_relation":
            score -= 8
            reasons.append("CodeQL이 관련 테스트 근거를 찾았습니다.")

        evidence.append(
            {
                "source": "codeql",
                "finding_type": finding.finding_type,
                "path": finding.impact_path,
                "confidence": finding.confidence,
                "query_id": finding.query_id,
                "reason": f"CodeQL {finding.finding_type} 근거입니다.",
            }
        )

    if reverse_affected_files:
        score += min(25, reverse_affected_files * 5)

    return score, reasons, evidence, queries


def _score_roles(roles: tuple[RoleMatch, ...]) -> tuple[int, list[str]]:
    if not roles:
        return 0, []
    criticality = highest_criticality(roles)
    score = CRITICALITY_SCORE.get(criticality, 0)
    reasons = [f"프로젝트 역할 매핑이 {criticality} 중요도에 도달했습니다."]
    tags = {tag for role in roles for tag in role.risk_tags}
    if {"correctness", "backwards_compatibility"} & tags:
        score += 12
        reasons.append("프로젝트 역할에 정확성 또는 하위 호환성 위험 태그가 있습니다.")
    return score, reasons


def _score_public_surface(
    findings: tuple[StaticImpactFindingInput, ...],
    roles: tuple[RoleMatch, ...],
    validation: tuple[ValidationSignal, ...],
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if any(finding.finding_type == "public_surface" for finding in findings):
        score += 15
        reasons.append("패키지 export 또는 공개 표면 근거 때문에 우선순위가 올라갑니다.")
    if any(role.role_id in {"public_api", "cli_entrypoint"} for role in roles):
        role_ids = {role.role_id for role in roles}
        if "public_api" in role_ids:
            score += 15
            reasons.append("프로젝트 역할 맵이 이 영역을 공개 API로 표시합니다.")
        if "cli_entrypoint" in role_ids:
            score += 12
            reasons.append("프로젝트 역할 맵이 이 영역을 CLI entrypoint로 표시합니다.")
    for signal in validation:
        if signal.signal_type == "docs_reference":
            score += 8
            reasons.append("문서가 영향을 받는 심볼을 참조합니다.")
        elif signal.signal_type == "examples_reference":
            score += 5
            reasons.append("예제가 영향을 받는 심볼을 참조합니다.")
        elif signal.signal_type == "entrypoint_reference":
            score += 12
            reasons.append("패키징 메타데이터가 CLI entrypoint를 노출합니다.")
        elif signal.signal_type == "package_export":
            score += 15
            reasons.append("검증 근거가 package export를 표시합니다.")
    return score, reasons


def _score_change_risk(changes: list[FileChangeInfo]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    total_changes = sum(change.changes for change in changes)
    if total_changes >= 200:
        score += 10
    if any(change.status in {"renamed", "removed", "deleted"} for change in changes):
        score += 8
        reasons.append("이름 변경/삭제 성격의 변경이라 호환성 검토가 필요합니다.")
    if any(
        category in {"config", "dependency", "migration"}
        for change in changes
        for category in classify_path(change.path)
    ):
        score += 15
        reasons.append("설정/의존성/빌드 관련 경로가 변경되었습니다.")
    return score, reasons


def _score_validation(signals: tuple[ValidationSignal, ...]) -> tuple[int, list[str]]:
    delta = 0
    reasons: list[str] = []
    for signal in signals:
        if signal.signal_type == "ci_test_result" and signal.status in {"passed", "related"}:
            delta -= 8
            reasons.append("관련 테스트 근거가 검증 위험을 낮춥니다.")
        elif signal.signal_type == "coverage_hint" and float(signal.value or 0) >= 0.8:
            delta -= 5
            reasons.append("커버리지 힌트가 불확실성을 낮춥니다.")
        elif signal.signal_type == "test_missing":
            delta += 8
            reasons.append("기대되는 테스트 근거가 없습니다.")
    return delta, reasons


def _static_paths(findings: tuple[StaticImpactFindingInput, ...]) -> list[dict[str, object]]:
    return [
        {
            "source_kind": "codeql",
            "finding_type": finding.finding_type,
            "start_symbol_key": finding.start_symbol_key,
            "end_symbol_key": finding.end_symbol_key,
            "path": finding.impact_path,
            "depth": max(0, len(finding.impact_path) - 1),
            "confidence": finding.confidence,
            "affected_file_path_ids": [finding.file_path_id],
            "affected_roles": finding.affected_roles,
            "related_tests": finding.related_tests,
            "query_id": finding.query_id,
        }
        for finding in findings
    ]


def _documentation_context(signals: tuple[ValidationSignal, ...]) -> list[dict[str, object]]:
    docs = []
    for signal in signals:
        if signal.signal_type in {"docs_reference", "examples_reference"}:
            docs.append(asdict(signal))
    return docs


def _public_surface_level(
    findings: tuple[StaticImpactFindingInput, ...],
    roles: tuple[RoleMatch, ...],
    categories: tuple[str, ...],
) -> str:
    if any(finding.finding_type == "public_surface" for finding in findings):
        return "public"
    if any(role.role_id in {"public_api", "cli_entrypoint"} for role in roles):
        return "public"
    if highest_criticality(roles) == "core":
        return "core_internal"
    if "test" in categories or "code" in categories:
        return "internal"
    return "low"


def _needs_validation(
    roles: tuple[RoleMatch, ...],
    findings: tuple[StaticImpactFindingInput, ...],
) -> bool:
    return highest_criticality(roles) in {"core", "important"} or any(
        finding.finding_type == "public_surface" for finding in findings
    )


def _has_hard_static(
    findings: tuple[StaticImpactFindingInput, ...],
    roles: tuple[RoleMatch, ...],
) -> bool:
    return any(finding.confidence >= 0.5 for finding in findings) or highest_criticality(roles) in {
        "core",
        "important",
    }


def _looks_like_code(path: str) -> bool:
    return path.endswith(".py") or "code" in classify_path(path)
