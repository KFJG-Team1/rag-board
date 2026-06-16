from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from pr_atlas_mvp.analysis.models import (
    CodeQLEvidence,
    SourceContext,
    ValidationSignal,
)


def collect_validation_signals(
    *,
    context: SourceContext,
    codeql_evidence: CodeQLEvidence,
    repo_root: Path | None,
    validation_evidence: Path | None,
) -> tuple[ValidationSignal, ...]:
    signals: list[ValidationSignal] = []
    if validation_evidence is not None and validation_evidence.exists():
        signals.extend(_load_validation_file(validation_evidence))

    if repo_root is not None and repo_root.exists():
        signals.extend(_collect_pyproject_entrypoints(repo_root))
        signals.extend(_collect_docs_references(repo_root, codeql_evidence))

    for finding in codeql_evidence.findings:
        if finding.finding_type == "test_relation":
            for related_test in finding.related_tests:
                signals.append(
                    ValidationSignal(
                        signal_type="ci_test_result",
                        target=str(related_test),
                        status="related",
                        source=finding.query_id,
                        confidence=finding.confidence,
                    )
                )
        if finding.finding_type == "public_surface":
            target = finding.end_symbol_key or finding.start_symbol_key or finding.query_id
            signals.append(
                ValidationSignal(
                    signal_type="package_export",
                    target=target,
                    source=finding.query_id,
                    confidence=finding.confidence,
                )
            )

    return tuple(_dedupe_signals(signals))


def _load_validation_file(path: Path) -> list[ValidationSignal]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("signals", payload if isinstance(payload, list) else [])
    signals: list[ValidationSignal] = []
    for row in rows:
        signals.append(
            ValidationSignal(
                signal_type=str(row["signal_type"]),
                target=str(row["target"]),
                status=row.get("status"),
                value=row.get("value"),
                source=row.get("source"),
                document_id=row.get("document_id"),
                confidence=float(row.get("confidence", 1.0)),
            )
        )
    return signals


def _collect_pyproject_entrypoints(repo_root: Path) -> list[ValidationSignal]:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return []
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    signals: list[ValidationSignal] = []

    project = payload.get("project", {})
    scripts = project.get("scripts", {}) or {}
    for name, target in scripts.items():
        signals.append(
            ValidationSignal(
                signal_type="entrypoint_reference",
                target=str(target),
                source=f"pyproject.toml:project.scripts.{name}",
                confidence=0.95,
            )
        )

    entrypoints = project.get("entry-points", {}) or {}
    for group, values in entrypoints.items():
        if isinstance(values, dict):
            for name, target in values.items():
                signals.append(
                    ValidationSignal(
                        signal_type="entrypoint_reference",
                        target=str(target),
                        source=f"pyproject.toml:project.entry-points.{group}.{name}",
                        confidence=0.95,
                    )
                )

    poetry_scripts = (
        payload.get("tool", {}).get("poetry", {}).get("scripts", {}) or {}
    )
    for name, target in poetry_scripts.items():
        signals.append(
            ValidationSignal(
                signal_type="entrypoint_reference",
                target=str(target),
                source=f"pyproject.toml:tool.poetry.scripts.{name}",
                confidence=0.9,
            )
        )

    return signals


def _collect_docs_references(
    repo_root: Path,
    codeql_evidence: CodeQLEvidence,
) -> list[ValidationSignal]:
    symbols = sorted(
        {
            change.symbol_name.split(".")[-1]
            for change in codeql_evidence.changes
            if change.symbol_name
        }
    )
    if not symbols:
        return []

    docs_paths = [
        path
        for path in repo_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".md", ".rst", ".txt"}
        and _is_supported_docs_path(path, repo_root)
    ]
    signals: list[ValidationSignal] = []
    for doc_path in docs_paths[:200]:
        try:
            content = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for symbol in symbols:
            if symbol and symbol in content:
                relative = doc_path.relative_to(repo_root).as_posix()
                signal_type = "examples_reference" if "example" in relative.lower() else "docs_reference"
                signals.append(
                    ValidationSignal(
                        signal_type=signal_type,
                        target=symbol,
                        document_id=f"docs:{relative}",
                        source=relative,
                        confidence=0.7,
                    )
                )
                break
    return signals[:50]


def _is_supported_docs_path(path: Path, repo_root: Path) -> bool:
    relative = path.relative_to(repo_root).as_posix().lower()
    return (
        relative.startswith("docs/")
        or relative.startswith("examples/")
        or relative.startswith("example/")
        or relative in {"readme.md", "readme.rst", "changelog.md", "changelog.rst"}
    )


def _dedupe_signals(signals: list[ValidationSignal]) -> list[ValidationSignal]:
    deduped: dict[tuple[str, str, str | None], ValidationSignal] = {}
    for signal in signals:
        key = (signal.signal_type, signal.target, signal.source or signal.document_id)
        existing = deduped.get(key)
        if existing is None or signal.confidence > existing.confidence:
            deduped[key] = signal
    return list(deduped.values())
