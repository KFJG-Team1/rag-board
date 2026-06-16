from __future__ import annotations

import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from platform import machine

from pr_atlas_mvp.analysis.artifacts import (
    ensure_repository_checkout,
    ensure_worktree,
    pull_request_artifact_paths,
    repository_artifact_paths,
)
from pr_atlas_mvp.analysis.codeql_parser import normalize_codeql_results, parse_codeql_results
from pr_atlas_mvp.analysis.models import (
    AnalysisRequest,
    CODEQL_QUERY_PROFILES,
    CodeQLEvidence,
    CodeQLRawResult,
    CodeQLSnapshotInfo,
    DEFAULT_CODEQL_QUERY_PROFILE,
    SourceContext,
)
from pr_atlas_mvp.analysis.progress import emit_progress


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERY_PACK = PROJECT_ROOT / "codeql" / "pr-impact"
QUERY_SUITES = {
    "lite": DEFAULT_QUERY_PACK / "codeql-suites" / "pr-impact-lite.qls",
    "full": DEFAULT_QUERY_PACK / "codeql-suites" / "pr-impact.qls",
}


def load_or_run_codeql_analysis(
    request: AnalysisRequest,
    context: SourceContext,
) -> CodeQLEvidence:
    if (
        request.repo_root is None
        and request.codeql_db is None
        and request.codeql_results is None
    ):
        return _load_or_run_automatic_codeql_analysis(request, context)
    return _load_or_run_manual_codeql_analysis(request, context)


def _load_or_run_manual_codeql_analysis(
    request: AnalysisRequest,
    context: SourceContext,
) -> CodeQLEvidence:
    query_profile = normalize_codeql_query_profile(request.codeql_query_profile)
    codeql_database_uri = str(request.codeql_db or "")
    errors: list[str] = []
    raw_results = ()
    status = "failed"

    if request.codeql_results is not None:
        try:
            raw_results = parse_codeql_results(
                request.codeql_results,
                request.query_pack_version,
            )
            status = "ready"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"CodeQL 결과를 파싱하지 못했습니다: {exc}")
    else:
        codeql_path = shutil.which("codeql")
        if codeql_path is None:
            errors.append("PATH에서 CodeQL CLI를 찾을 수 없습니다.")
        elif request.codeql_db is None and request.repo_root is None:
            errors.append("CodeQL 분석에는 --codeql-db 또는 --repo-root가 필요합니다.")
        else:
            try:
                codeql_database_uri, results_path = _run_codeql_cli(
                    codeql_path=codeql_path,
                    request=request,
                )
                raw_results = parse_codeql_results(results_path, request.query_pack_version)
                status = "ready"
            except subprocess.CalledProcessError as exc:
                status = "partial"
                errors.append(
                    "CodeQL 명령이 실패했습니다: "
                    f"{' '.join(str(part) for part in exc.cmd)}\n{exc.stderr or exc.stdout or ''}"
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"CodeQL 분석이 실패했습니다: {exc}")

    if raw_results and errors:
        status = "partial"

    changes, findings = normalize_codeql_results(raw_results, context)
    snapshot = CodeQLSnapshotInfo(
        id=None,
        repository_id=context.repository_id,
        commit_sha=context.analyzed_commit_sha,
        codeql_database_uri=codeql_database_uri,
        query_pack_version=request.query_pack_version,
        status=status,
        metadata={
            "raw_result_count": len(raw_results),
            "change_count": len(changes),
            "finding_count": len(findings),
            "errors": errors,
            "query_pack": str(DEFAULT_QUERY_PACK),
            "codeql_query_profile": query_profile,
            "query_suite": str(codeql_query_suite_for_profile(query_profile)),
        },
    )
    return CodeQLEvidence(
        snapshot=snapshot,
        changes=changes,
        findings=findings,
        errors=tuple(errors),
    )


def _load_or_run_automatic_codeql_analysis(
    request: AnalysisRequest,
    context: SourceContext,
) -> CodeQLEvidence:
    emit_progress("codeql_prepare", "자동 CodeQL 분석 산출물 경로를 확인합니다.", percent=30)
    query_profile = normalize_codeql_query_profile(request.codeql_query_profile)
    codeql_path = shutil.which("codeql")
    errors: list[str] = []
    raw_results: list[CodeQLRawResult] = []
    per_pr: list[dict[str, str | int]] = []
    codeql_database_uri = str(repository_artifact_paths(request.owner, request.repo).codeql_dbs)

    if codeql_path is None:
        errors.append("PATH에서 CodeQL CLI를 찾을 수 없습니다.")
        emit_progress("codeql_prepare", "PATH에서 CodeQL CLI를 찾지 못했습니다.", percent=32, status="failed")
    else:
        try:
            emit_progress("codeql_checkout", "레포지토리 checkout을 준비합니다.", percent=34)
            repository_path = ensure_repository_checkout(request.owner, request.repo)
            emit_progress("codeql_checkout", "레포지토리 checkout 준비가 완료되었습니다.", percent=38, status="succeeded")
        except Exception as exc:  # noqa: BLE001
            repository_path = None
            errors.append(f"레포지토리 checkout 준비가 실패했습니다: {exc}")
            emit_progress("codeql_checkout", "레포지토리 checkout 준비가 실패했습니다.", percent=38, status="failed")

        if repository_path is not None:
            total_prs = max(1, len(context.pull_requests))
            for index, pull_request in enumerate(context.pull_requests, start=1):
                base_percent = 40 + int((index - 1) * 26 / total_prs)
                if not pull_request.head_sha:
                    errors.append(f"PR #{pull_request.number}에 head SHA가 없습니다.")
                    emit_progress(
                        "codeql_pr_prepare",
                        f"PR #{pull_request.number}에 head SHA가 없어 건너뜁니다.",
                        percent=base_percent,
                        pr_number=pull_request.number,
                        status="failed",
                    )
                    continue
                paths = pull_request_artifact_paths(
                    owner=request.owner,
                    repo=request.repo,
                    pr_number=pull_request.number,
                    head_sha=pull_request.head_sha,
                    query_pack_version=request.query_pack_version,
                    codeql_query_profile=query_profile,
                )
                try:
                    emit_progress(
                        "codeql_worktree",
                        f"PR #{pull_request.number} worktree를 준비합니다.",
                        percent=base_percent,
                        pr_number=pull_request.number,
                    )
                    ensure_worktree(repository_path, paths.worktree, pull_request.head_sha)
                    emit_progress(
                        "codeql_analyze",
                        f"PR #{pull_request.number} CodeQL DB/results를 준비합니다.",
                        percent=min(66, base_percent + 8),
                        pr_number=pull_request.number,
                    )
                    results_path = _run_codeql_cli_for_paths(
                        codeql_path=codeql_path,
                        source_root=paths.worktree,
                        database_path=paths.codeql_db,
                        output_path=paths.codeql_results,
                        codeql_query_profile=query_profile,
                    )
                    parsed_results = parse_codeql_results(
                        results_path,
                        request.query_pack_version,
                    )
                    raw_results.extend(parsed_results)
                    emit_progress(
                        "codeql_analyze",
                        f"PR #{pull_request.number} CodeQL 결과 파싱이 완료되었습니다.",
                        percent=min(68, base_percent + 14),
                        pr_number=pull_request.number,
                        status="succeeded",
                    )
                    per_pr.append(
                        {
                            "pr_number": pull_request.number,
                            "head_sha": pull_request.head_sha,
                            "worktree": str(paths.worktree),
                            "codeql_db": str(paths.codeql_db),
                            "codeql_results": str(paths.codeql_results),
                            "codeql_query_profile": query_profile,
                        }
                    )
                except subprocess.CalledProcessError as exc:
                    errors.append(
                        "CodeQL 명령이 실패했습니다: "
                        f"PR #{pull_request.number}: {' '.join(str(part) for part in exc.cmd)}\n"
                        f"{exc.stderr or exc.stdout or ''}"
                    )
                    emit_progress(
                        "codeql_analyze",
                        f"PR #{pull_request.number} CodeQL 명령이 실패했습니다.",
                        percent=min(68, base_percent + 14),
                        pr_number=pull_request.number,
                        status="failed",
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"PR #{pull_request.number} CodeQL 분석이 실패했습니다: {exc}")
                    emit_progress(
                        "codeql_analyze",
                        f"PR #{pull_request.number} CodeQL 분석이 실패했습니다.",
                        percent=min(68, base_percent + 14),
                        pr_number=pull_request.number,
                        status="failed",
                    )

    if raw_results and errors:
        status = "partial"
    elif raw_results:
        status = "ready"
    else:
        status = "failed"

    changes, findings = normalize_codeql_results(tuple(raw_results), context)
    emit_progress("codeql_normalize", "CodeQL 근거 정규화가 완료되었습니다.", percent=69, status=status)
    snapshot = CodeQLSnapshotInfo(
        id=None,
        repository_id=context.repository_id,
        commit_sha=context.analyzed_commit_sha,
        codeql_database_uri=codeql_database_uri,
        query_pack_version=request.query_pack_version,
        status=status,
        metadata={
            "mode": "automatic",
            "raw_result_count": len(raw_results),
            "change_count": len(changes),
            "finding_count": len(findings),
            "errors": errors,
            "per_pr": per_pr,
            "query_pack": str(DEFAULT_QUERY_PACK),
            "codeql_query_profile": query_profile,
            "query_suite": str(codeql_query_suite_for_profile(query_profile)),
        },
    )
    return CodeQLEvidence(
        snapshot=snapshot,
        changes=changes,
        findings=findings,
        errors=tuple(errors),
    )


def _run_codeql_cli(
    *,
    codeql_path: str,
    request: AnalysisRequest,
) -> tuple[str, Path]:
    codeql_command = build_codeql_base_command(codeql_path)
    if request.codeql_db is not None:
        database_path = request.codeql_db
    else:
        database_path = Path(tempfile.mkdtemp(prefix="pr-atlas-codeql-db-"))
        subprocess.run(
            [
                *codeql_command,
                "database",
                "create",
                str(database_path),
                "--language=python",
                "--source-root",
                str(request.repo_root),
                "--overwrite",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

    if not database_path.exists():
        raise FileNotFoundError(f"CodeQL database가 없습니다: {database_path}")

    output_path = Path(tempfile.mkdtemp(prefix="pr-atlas-codeql-results-")) / "results.sarif"
    subprocess.run(
        build_codeql_analyze_command(
            codeql_command=codeql_command,
            database_path=database_path,
            output_path=output_path,
            codeql_query_profile=request.codeql_query_profile,
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    return str(database_path), output_path


def _run_codeql_cli_for_paths(
    *,
    codeql_path: str,
    source_root: Path,
    database_path: Path,
    output_path: Path,
    codeql_query_profile: str = DEFAULT_CODEQL_QUERY_PROFILE,
) -> Path:
    codeql_command = build_codeql_base_command(codeql_path)
    if not database_path.exists():
        database_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                *codeql_command,
                "database",
                "create",
                str(database_path),
                "--language=python",
                "--source-root",
                str(source_root),
                "--overwrite",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

    if not database_path.exists():
        raise FileNotFoundError(f"CodeQL database가 없습니다: {database_path}")

    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            build_codeql_analyze_command(
                codeql_command=codeql_command,
                database_path=database_path,
                output_path=output_path,
                codeql_query_profile=codeql_query_profile,
            ),
            check=True,
            text=True,
            capture_output=True,
        )
    return output_path


def build_codeql_base_command(
    codeql_path: str,
    *,
    platform_name: str | None = None,
    machine_name: str | None = None,
) -> list[str]:
    platform_name = platform_name or sys.platform
    machine_name = machine_name or machine()
    if platform_name == "darwin" and machine_name == "arm64":
        return ["/usr/bin/arch", "-x86_64", codeql_path]
    return [codeql_path]


def build_codeql_analyze_command(
    *,
    codeql_path: str | None = None,
    codeql_command: list[str] | None = None,
    database_path: Path,
    output_path: Path,
    codeql_query_profile: str = DEFAULT_CODEQL_QUERY_PROFILE,
) -> list[str]:
    if codeql_command is None:
        if codeql_path is None:
            raise ValueError("codeql_path or codeql_command is required.")
        codeql_command = build_codeql_base_command(codeql_path)

    query_suite = codeql_query_suite_for_profile(codeql_query_profile)
    return [
        *codeql_command,
        "database",
        "analyze",
        str(database_path),
        str(query_suite),
        "--format=sarif-latest",
        f"--output={output_path}",
    ]


def normalize_codeql_query_profile(profile: str | None) -> str:
    normalized = (profile or DEFAULT_CODEQL_QUERY_PROFILE).strip().lower()
    if normalized not in CODEQL_QUERY_PROFILES:
        allowed = ", ".join(CODEQL_QUERY_PROFILES)
        raise ValueError(
            f"Unsupported CodeQL query profile: {profile!r}. Expected one of: {allowed}."
        )
    return normalized


def codeql_query_suite_for_profile(profile: str | None) -> Path:
    return QUERY_SUITES[normalize_codeql_query_profile(profile)]
