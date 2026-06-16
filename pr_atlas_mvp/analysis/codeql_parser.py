from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pr_atlas_mvp.analysis.deterministic import hunk_ranges_overlap
from pr_atlas_mvp.analysis.models import (
    CodeQLChangeInput,
    CodeQLRawResult,
    FileChangeInfo,
    SourceContext,
    StaticImpactFindingInput,
)


SYMBOL_DEFINITION_IDS = {
    "pr-impact/symbol-definitions",
    "pr-impact/class-definitions",
    "py/symbol-definitions",
    "py/class-definitions",
    "symbol-definitions",
    "class-definitions",
}


def parse_codeql_results(path: Path, query_version: str) -> tuple[CodeQLRawResult, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "runs" in payload:
        return parse_sarif(payload, query_version)
    if isinstance(payload, list):
        return tuple(_raw_from_json_row(row, query_version) for row in payload)
    if "results" in payload and isinstance(payload["results"], list):
        return tuple(_raw_from_json_row(row, query_version) for row in payload["results"])
    raise ValueError(f"Unsupported CodeQL result format: {path}")


def parse_sarif(payload: dict[str, Any], query_version: str) -> tuple[CodeQLRawResult, ...]:
    results: list[CodeQLRawResult] = []
    for run in payload.get("runs", []):
        rule_versions = {
            rule.get("id"): rule.get("properties", {}).get("queryVersion", query_version)
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
        }
        for result in run.get("results", []):
            location = _primary_location(result)
            message = result.get("message", {}).get("text", "")
            query_id = result.get("ruleId", "unknown")
            results.append(
                CodeQLRawResult(
                    query_id=query_id,
                    query_version=rule_versions.get(query_id, query_version),
                    path=location.get("path"),
                    start_line=location.get("start_line"),
                    end_line=location.get("end_line"),
                    message=message,
                    payload=_extract_json_payload(message),
                )
            )
    return tuple(results)


def normalize_codeql_results(
    raw_results: tuple[CodeQLRawResult, ...],
    context: SourceContext,
) -> tuple[tuple[CodeQLChangeInput, ...], tuple[StaticImpactFindingInput, ...]]:
    changes: list[CodeQLChangeInput] = []
    findings: list[StaticImpactFindingInput] = []

    for raw in raw_results:
        record_type = raw.payload.get("record_type")
        if record_type == "symbol_definition" or raw.query_id in SYMBOL_DEFINITION_IDS:
            changes.extend(_map_symbol_definition(raw, context))
        else:
            finding = _map_static_finding(raw, context)
            if finding is not None:
                findings.append(finding)

    return tuple(_dedupe_changes(changes)), tuple(_dedupe_findings(findings))


def _map_symbol_definition(
    raw: CodeQLRawResult,
    context: SourceContext,
) -> list[CodeQLChangeInput]:
    if raw.path is None:
        return []
    path = _normalize_path(raw.path)
    file_changes = [file for file in context.file_changes if file.path == path]
    if not file_changes:
        return []

    symbol_name = str(raw.payload.get("symbol_name") or raw.payload.get("name") or path)
    symbol_kind = str(raw.payload.get("symbol_kind") or raw.payload.get("kind") or "symbol")
    symbol_key = str(
        raw.payload.get("symbol_key") or f"codeql:symbol:{path}:{symbol_name}"
    )
    raw_start = int(raw.start_line or raw.payload.get("start_line") or 1)
    raw_end = int(raw.end_line or raw.payload.get("end_line") or raw_start)

    mapped: list[CodeQLChangeInput] = []
    hunks_by_file = [hunk for hunk in context.hunks if hunk.path == path]
    for file_change in file_changes:
        matching_hunks = [
            hunk
            for hunk in hunks_by_file
            if hunk.pull_request_id == file_change.pull_request_id
            and _line_ranges_overlap(hunk.new_start, hunk.new_end, raw_start, raw_end + 1)
        ]
        if matching_hunks:
            for hunk in matching_hunks:
                mapped.append(
                    _change_from_symbol(raw, file_change, symbol_key, symbol_name, symbol_kind, hunk.id, 0.9)
                )
        elif not hunks_by_file and file_change.patch is None:
            mapped.append(
                _change_from_symbol(raw, file_change, symbol_key, symbol_name, symbol_kind, None, 0.6)
            )
        else:
            near_hunks = [
                hunk
                for hunk in hunks_by_file
                if hunk.pull_request_id == file_change.pull_request_id
                and abs(hunk.new_start - raw_start) <= 80
            ]
            for hunk in near_hunks[:1]:
                mapped.append(
                    _change_from_symbol(raw, file_change, symbol_key, symbol_name, symbol_kind, hunk.id, 0.65)
                )

    return mapped


def _change_from_symbol(
    raw: CodeQLRawResult,
    file_change: FileChangeInfo,
    symbol_key: str,
    symbol_name: str,
    symbol_kind: str,
    hunk_id: int | None,
    confidence: float,
) -> CodeQLChangeInput:
    change_type = str(raw.payload.get("change_type") or _change_type_from_status(file_change.status))
    return CodeQLChangeInput(
        pull_request_id=file_change.pull_request_id,
        file_path_id=file_change.file_path_id,
        hunk_id=hunk_id,
        symbol_key=symbol_key,
        symbol_name=symbol_name,
        symbol_kind=symbol_kind,
        change_type=change_type,
        confidence=confidence,
        metadata={
            "query_id": raw.query_id,
            "query_version": raw.query_version,
            "path": file_change.path,
            "location": {
                "start_line": raw.start_line,
                "end_line": raw.end_line,
            },
            "payload": raw.payload,
        },
    )


def _map_static_finding(
    raw: CodeQLRawResult,
    context: SourceContext,
) -> StaticImpactFindingInput | None:
    path = _normalize_path(raw.payload.get("primary_path") or raw.path or "")
    file_change = _find_file_change_for_path(path, context)
    if file_change is None:
        affected_paths = [str(value) for value in raw.payload.get("affected_paths", [])]
        for affected_path in affected_paths:
            file_change = _find_file_change_for_path(_normalize_path(affected_path), context)
            if file_change is not None:
                break
    if file_change is None and context.file_changes:
        file_change = context.file_changes[0]
    if file_change is None:
        return None

    finding_type = str(raw.payload.get("finding_type") or _finding_type_from_query_id(raw.query_id))
    confidence = float(raw.payload.get("confidence", 0.8))
    start_symbol_key = raw.payload.get("start_symbol_key")
    end_symbol_key = raw.payload.get("end_symbol_key")
    impact_path = raw.payload.get("impact_path")
    if not isinstance(impact_path, list):
        impact_path = [value for value in (start_symbol_key, end_symbol_key) if value]
    affected_paths = raw.payload.get("affected_paths")
    if not isinstance(affected_paths, list):
        affected_paths = [file_change.path]
    related_tests = raw.payload.get("related_tests")
    if not isinstance(related_tests, list):
        related_tests = []
    affected_roles = raw.payload.get("affected_roles")
    if not isinstance(affected_roles, list):
        affected_roles = []

    return StaticImpactFindingInput(
        repository_id=context.repository_id,
        pull_request_id=file_change.pull_request_id,
        file_path_id=file_change.file_path_id,
        finding_type=finding_type,
        start_symbol_key=str(start_symbol_key) if start_symbol_key else None,
        end_symbol_key=str(end_symbol_key) if end_symbol_key else None,
        impact_path=impact_path,
        affected_paths=affected_paths,
        affected_roles=affected_roles,
        related_tests=related_tests,
        confidence=confidence,
        query_id=raw.query_id,
        query_version=raw.query_version,
        metadata={
            "message": raw.message,
            "location": {
                "path": raw.path,
                "start_line": raw.start_line,
                "end_line": raw.end_line,
            },
            "payload": raw.payload,
        },
    )


def _raw_from_json_row(row: dict[str, Any], query_version: str) -> CodeQLRawResult:
    message = str(row.get("message") or row.get("reason") or "")
    payload = dict(row.get("payload") or {})
    for key, value in row.items():
        if key not in {"payload", "message"}:
            payload.setdefault(key, value)
    return CodeQLRawResult(
        query_id=str(row.get("query_id") or row.get("ruleId") or "unknown"),
        query_version=str(row.get("query_version") or query_version),
        path=row.get("path"),
        start_line=row.get("start_line"),
        end_line=row.get("end_line"),
        message=message,
        payload=payload,
    )


def _primary_location(result: dict[str, Any]) -> dict[str, Any]:
    locations = result.get("locations") or []
    if not locations:
        return {}
    physical = locations[0].get("physicalLocation", {})
    artifact = physical.get("artifactLocation", {})
    region = physical.get("region", {})
    return {
        "path": artifact.get("uri"),
        "start_line": region.get("startLine"),
        "end_line": region.get("endLine") or region.get("startLine"),
    }


def _extract_json_payload(message: str) -> dict[str, Any]:
    if not message:
        return {}
    start = message.find("{")
    end = message.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        payload = json.loads(message[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _line_ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return left_start < right_end and right_start < left_end


def _change_type_from_status(status: str) -> str:
    if status == "added":
        return "added"
    if status in {"removed", "deleted"}:
        return "deleted"
    return "modified"


def _finding_type_from_query_id(query_id: str) -> str:
    lowered = query_id.lower()
    if "public" in lowered or "export" in lowered:
        return "public_surface"
    if "test" in lowered:
        return "test_relation"
    if "data" in lowered:
        return "data_flow"
    if "control" in lowered:
        return "control_flow"
    if "reference" in lowered or "call" in lowered or "dependency" in lowered:
        return "reverse_dependency"
    return "uncertainty"


def _find_file_change_for_path(path: str, context: SourceContext) -> FileChangeInfo | None:
    for file_change in context.file_changes:
        if file_change.path == path:
            return file_change
    return None


def _dedupe_changes(changes: list[CodeQLChangeInput]) -> list[CodeQLChangeInput]:
    deduped: dict[tuple[int, int, int | None, str], CodeQLChangeInput] = {}
    for change in changes:
        key = (
            change.pull_request_id,
            change.file_path_id,
            change.hunk_id,
            change.symbol_key,
        )
        existing = deduped.get(key)
        if existing is None or change.confidence > existing.confidence:
            deduped[key] = change
    return list(deduped.values())


def _dedupe_findings(findings: list[StaticImpactFindingInput]) -> list[StaticImpactFindingInput]:
    deduped: dict[tuple[int, int, str, str | None, str | None], StaticImpactFindingInput] = {}
    for finding in findings:
        key = (
            finding.pull_request_id,
            finding.file_path_id,
            finding.finding_type,
            finding.start_symbol_key,
            finding.end_symbol_key,
        )
        existing = deduped.get(key)
        if existing is None or finding.confidence > existing.confidence:
            deduped[key] = finding
    return list(deduped.values())
