from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from pr_atlas_mvp.analysis.models import AnalysisRequest
from pr_atlas_mvp.analysis.pipeline import run_analysis
from pr_atlas_mvp.analysis.progress import progress_reporter
from pr_atlas_mvp.api.config import (
    get_database_url,
    get_openai_model,
    get_openai_timeout_seconds,
    is_openai_configured,
)
from pr_atlas_mvp.api.schemas import AnalysisRunRequest
from pr_atlas_mvp.api.services import LLMConfigurationError
from pr_atlas_mvp.postgres.connection import connect_database


class AnalysisJobNotFoundError(RuntimeError):
    pass


@dataclass
class AnalysisJob:
    job_id: str
    owner: str
    repo: str
    pr_numbers: list[int]
    request: AnalysisRunRequest
    status: str = "queued"
    current_step: str | None = None
    percent: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class AnalysisJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pr-atlas-analysis")

    def start(self, request: AnalysisRunRequest) -> dict[str, Any]:
        if request.use_llm and not is_openai_configured():
            raise LLMConfigurationError("OPENAI_API_KEY is required for LLM analysis.")

        job = AnalysisJob(
            job_id=uuid.uuid4().hex,
            owner=request.owner,
            repo=request.repo,
            pr_numbers=list(request.pr_numbers),
            request=request,
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._append_event_locked(
                job,
                {
                    "stage": "queued",
                    "message": "분석 job이 대기열에 등록되었습니다.",
                    "status": "queued",
                    "percent": 0,
                },
            )
        self._executor.submit(self._run, job.job_id)
        return self._job_start_payload(job)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise AnalysisJobNotFoundError(f"Analysis job not found: {job_id}")
            return self._job_payload(job)

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            self._append_event_locked(
                job,
                {
                    "stage": "start",
                    "message": "분석을 시작합니다.",
                    "status": "running",
                    "percent": 1,
                },
            )

        def report(event: dict[str, Any]) -> None:
            with self._lock:
                current = self._jobs[job_id]
                self._append_event_locked(current, event)

        session = None
        try:
            database_url = get_database_url()
            if not database_url:
                raise RuntimeError("DATABASE_URL is not configured.")
            session = connect_database(database_url)
            analysis_request = _to_analysis_request(job.request)
            with progress_reporter(report):
                state = run_analysis(session, analysis_request)
            session.commit()
            with self._lock:
                current = self._jobs[job_id]
                current.status = "succeeded"
                current.percent = 100
                current.current_step = "분석 완료"
                current.result = state.outputs
                current.finished_at = datetime.now(UTC)
                self._append_event_locked(
                    current,
                    {
                        "stage": "complete",
                        "message": "분석이 완료되었습니다.",
                        "status": "succeeded",
                        "percent": 100,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            if session is not None:
                session.rollback()
            with self._lock:
                current = self._jobs[job_id]
                current.status = "failed"
                current.error = str(exc)
                current.finished_at = datetime.now(UTC)
                self._append_event_locked(
                    current,
                    {
                        "stage": "failed",
                        "message": "분석이 실패했습니다.",
                        "status": "failed",
                        "percent": current.percent,
                    },
                )
        finally:
            if session is not None:
                session.close()

    def _append_event_locked(self, job: AnalysisJob, event: dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(UTC),
            "stage": str(event.get("stage", "unknown")),
            "message": str(event.get("message", "")),
            "status": str(event.get("status", "running")),
            "percent": event.get("percent"),
            "pr_number": event.get("pr_number"),
        }
        if isinstance(payload["percent"], int):
            job.percent = max(job.percent, max(0, min(100, payload["percent"])))
        job.current_step = payload["message"]
        job.events.append(payload)
        if len(job.events) > 200:
            job.events = job.events[-200:]

    def _job_start_payload(self, job: AnalysisJob) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "owner": job.owner,
            "repo": job.repo,
            "pr_numbers": job.pr_numbers,
        }

    def _job_payload(self, job: AnalysisJob) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "owner": job.owner,
            "repo": job.repo,
            "pr_numbers": job.pr_numbers,
            "current_step": job.current_step,
            "percent": job.percent,
            "events": list(job.events),
            "result": job.result,
            "error": job.error,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }


def _to_analysis_request(request: AnalysisRunRequest) -> AnalysisRequest:
    role_map = request.project_role_map
    if role_map is None and request.repo_root is not None:
        candidate = request.repo_root / "project-role-map.yaml"
        role_map = candidate if candidate.exists() else None
    return AnalysisRequest(
        owner=request.owner,
        repo=request.repo,
        pr_numbers=tuple(request.pr_numbers),
        repo_root=request.repo_root,
        codeql_db=request.codeql_db,
        codeql_results=request.codeql_results,
        project_role_map=role_map,
        validation_evidence=request.validation_evidence,
        query_pack_version=request.query_pack_version,
        codeql_query_profile=request.codeql_query_profile,
        use_llm=request.use_llm,
        llm_model=get_openai_model(),
        llm_timeout_seconds=get_openai_timeout_seconds(),
        create_schema=not request.skip_schema,
    )


analysis_job_manager = AnalysisJobManager()
