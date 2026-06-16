from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import yaml

from pr_atlas_mvp.analysis.deterministic import classify_path
from pr_atlas_mvp.analysis.models import (
    ProjectRole,
    ProjectRoleMap,
    RoleMatch,
    StaticImpactFindingInput,
)


DEFAULT_ROLES = ProjectRoleMap(
    version=1,
    is_default=True,
    roles=(
        ProjectRole(
            role_id="docs_examples",
            name="문서와 예제",
            criticality="low",
            paths=("README*", "docs/**", "examples/**", "*.md", "*.rst"),
        ),
        ProjectRole(
            role_id="tests",
            name="테스트",
            criticality="internal",
            paths=("tests/**", "test/**", "*test*", "*spec*"),
        ),
        ProjectRole(
            role_id="dependency_config",
            name="의존성과 설정",
            criticality="important",
            paths=(
                "pyproject.toml",
                "requirements*.txt",
                "setup.py",
                "setup.cfg",
                "*.lock",
                ".github/**",
            ),
            risk_tags=("dependency", "configuration"),
        ),
        ProjectRole(
            role_id="source_code",
            name="소스 코드",
            criticality="internal",
            paths=("src/**", "**/*.py"),
        ),
    ),
)


def load_project_role_map(path: Path | None) -> ProjectRoleMap:
    if path is None or not path.exists():
        return DEFAULT_ROLES
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    roles = tuple(_role_from_payload(role) for role in payload.get("roles", []))
    return ProjectRoleMap(
        version=int(payload.get("version", 1)),
        roles=roles,
        source_path=str(path),
        is_default=False,
    )


def match_roles_for_file(
    path: str,
    *,
    role_map: ProjectRoleMap,
    static_findings: tuple[StaticImpactFindingInput, ...] = (),
    symbol_names: tuple[str, ...] = (),
) -> tuple[RoleMatch, ...]:
    matches: list[RoleMatch] = []
    normalized = path.replace("\\", "/")

    for role in role_map.roles:
        path_reason = _match_path(role, normalized)
        if path_reason:
            matches.append(_role_match(role, path_reason))
            continue

        symbol_reason = _match_symbol(role, symbol_names)
        if symbol_reason:
            matches.append(_role_match(role, symbol_reason))
            continue

        finding_reason = _match_static_finding(role, static_findings)
        if finding_reason:
            matches.append(_role_match(role, finding_reason))

    if not matches and role_map.is_default:
        categories = classify_path(path)
        if "code" in categories:
            role = _role_by_id(role_map, "source_code")
            if role is not None:
                matches.append(_role_match(role, "기본 코드 경로 역할로 분류됨"))

    return tuple(_dedupe_role_matches(matches))


def highest_criticality(matches: tuple[RoleMatch, ...]) -> str:
    order = {"low": 0, "internal": 1, "important": 2, "core": 3}
    if not matches:
        return "low"
    return max((match.criticality for match in matches), key=lambda item: order.get(item, 0))


def _role_from_payload(payload: dict[str, Any]) -> ProjectRole:
    return ProjectRole(
        role_id=str(payload["role_id"]),
        name=str(payload.get("name") or payload["role_id"]),
        criticality=str(payload.get("criticality") or "internal"),
        paths=tuple(str(value) for value in payload.get("paths", []) or []),
        public_api=tuple(str(value) for value in payload.get("public_api", []) or []),
        entrypoints=tuple(str(value) for value in payload.get("entrypoints", []) or []),
        docs=tuple(str(value) for value in payload.get("docs", []) or []),
        risk_tags=tuple(str(value) for value in payload.get("risk_tags", []) or []),
    )


def _match_path(role: ProjectRole, path: str) -> str | None:
    for pattern in role.paths:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.lower(), pattern.lower()):
            return f"경로가 {pattern} 패턴과 일치합니다"
    return None


def _match_symbol(role: ProjectRole, symbol_names: tuple[str, ...]) -> str | None:
    for symbol_name in symbol_names:
        for public_api in role.public_api:
            if symbol_name == public_api or symbol_name.endswith(public_api):
                return f"심볼이 공개 API {public_api}와 일치합니다"
        for entrypoint in role.entrypoints:
            if symbol_name == entrypoint or symbol_name.endswith(entrypoint):
                return f"심볼이 entrypoint {entrypoint}와 일치합니다"
    return None


def _match_static_finding(
    role: ProjectRole,
    static_findings: tuple[StaticImpactFindingInput, ...],
) -> str | None:
    for finding in static_findings:
        values = [
            str(value)
            for value in (
                finding.start_symbol_key,
                finding.end_symbol_key,
                *finding.impact_path,
                *finding.affected_roles,
            )
            if value
        ]
        for value in values:
            if value == role.role_id or value.endswith(role.role_id):
                return f"CodeQL 결과가 역할 {role.role_id}를 참조합니다"
            for public_api in role.public_api:
                if public_api in value:
                    return f"CodeQL 결과가 공개 API {public_api}를 참조합니다"
            for entrypoint in role.entrypoints:
                if entrypoint in value:
                    return f"CodeQL 결과가 entrypoint {entrypoint}를 참조합니다"
    return None


def _role_match(role: ProjectRole, reason: str) -> RoleMatch:
    return RoleMatch(
        role_id=role.role_id,
        name=role.name,
        criticality=role.criticality,
        match_reason=reason,
        risk_tags=role.risk_tags,
    )


def _role_by_id(role_map: ProjectRoleMap, role_id: str) -> ProjectRole | None:
    for role in role_map.roles:
        if role.role_id == role_id:
            return role
    return None


def _dedupe_role_matches(matches: list[RoleMatch]) -> list[RoleMatch]:
    deduped: dict[str, RoleMatch] = {}
    for match in matches:
        deduped.setdefault(match.role_id, match)
    return list(deduped.values())
