from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pr_atlas_mvp.analysis.models import (
    CodeQLChangeInput,
    CodeQLSnapshotInfo,
    StaticImpactFindingInput,
)
from pr_atlas_mvp.postgres.schema import (
    PullRequestCodeqlChange,
    StaticAnalysisSnapshot,
    StaticImpactFinding,
)


def upsert_static_analysis_snapshot(
    session: Session,
    snapshot: CodeQLSnapshotInfo,
) -> StaticAnalysisSnapshot:
    row = session.scalar(
        select(StaticAnalysisSnapshot).where(
            StaticAnalysisSnapshot.repository_id == snapshot.repository_id,
            StaticAnalysisSnapshot.commit_sha == snapshot.commit_sha,
            StaticAnalysisSnapshot.codeql_database_uri == snapshot.codeql_database_uri,
            StaticAnalysisSnapshot.query_pack_version == snapshot.query_pack_version,
        )
    )
    values = {
        "status": snapshot.status,
        "details": dict(snapshot.metadata),
    }
    if row is None:
        row = StaticAnalysisSnapshot(
            repository_id=snapshot.repository_id,
            commit_sha=snapshot.commit_sha,
            codeql_database_uri=snapshot.codeql_database_uri,
            query_pack_version=snapshot.query_pack_version,
            **values,
        )
        session.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)

    session.flush()
    return row


def replace_static_evidence(
    session: Session,
    *,
    snapshot_id: int,
    pull_request_ids: tuple[int, ...],
    changes: tuple[CodeQLChangeInput, ...],
    findings: tuple[StaticImpactFindingInput, ...],
) -> None:
    session.execute(
        delete(PullRequestCodeqlChange).where(
            PullRequestCodeqlChange.snapshot_id == snapshot_id,
            PullRequestCodeqlChange.pull_request_id.in_(pull_request_ids),
        )
    )
    session.execute(
        delete(StaticImpactFinding).where(
            StaticImpactFinding.snapshot_id == snapshot_id,
            StaticImpactFinding.pull_request_id.in_(pull_request_ids),
        )
    )

    for change in changes:
        session.add(
            PullRequestCodeqlChange(
                pull_request_id=change.pull_request_id,
                file_path_id=change.file_path_id,
                hunk_id=change.hunk_id,
                snapshot_id=snapshot_id,
                symbol_key=change.symbol_key,
                symbol_name=change.symbol_name,
                symbol_kind=change.symbol_kind,
                change_type=change.change_type,
                confidence=change.confidence,
                details=dict(change.metadata),
            )
        )

    for finding in findings:
        session.add(
            StaticImpactFinding(
                repository_id=finding.repository_id,
                pull_request_id=finding.pull_request_id,
                file_path_id=finding.file_path_id,
                snapshot_id=snapshot_id,
                finding_type=finding.finding_type,
                start_symbol_key=finding.start_symbol_key,
                end_symbol_key=finding.end_symbol_key,
                impact_path=list(finding.impact_path),
                affected_paths=list(finding.affected_paths),
                affected_roles=list(finding.affected_roles),
                related_tests=list(finding.related_tests),
                confidence=finding.confidence,
                query_id=finding.query_id,
                query_version=finding.query_version,
                details=dict(finding.metadata),
            )
        )
