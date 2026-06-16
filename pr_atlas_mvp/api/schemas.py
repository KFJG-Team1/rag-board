from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pr_atlas_mvp.analysis.models import (
    DEFAULT_CODEQL_QUERY_PROFILE,
    DEFAULT_QUERY_PACK_VERSION,
)


class HealthResponse(BaseModel):
    status: str
    api_version: str
    database_url_configured: bool
    codeql_available: bool
    codeql_path: str | None = None
    llm_configured: bool
    llm_model: str


class RepositorySummary(BaseModel):
    id: int
    repo_key: str
    owner: str
    name: str
    pull_request_count: int
    last_imported_at: datetime | None = None
    artifact_status: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RepositoryListResponse(BaseModel):
    repositories: list[RepositorySummary]
    limit: int
    offset: int
    total: int


class RepositoryDetailResponse(BaseModel):
    repository: RepositorySummary
    artifact_status: dict[str, Any]


class RepositoryImportRequest(BaseModel):
    owner: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    repo: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    state: Literal["open", "closed", "all"] = "open"
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=30, ge=1, le=100)


class RepositoryImportResponse(BaseModel):
    repository: RepositorySummary
    imported_pr_count: int
    state: Literal["open", "closed", "all"]
    page: int
    limit: int
    message: str


class ChangedFileSummary(BaseModel):
    file_path_id: int
    path: str
    status: str
    additions: int
    deletions: int
    changes: int
    hunk_count: int = 0
    patch_excerpt: str | None = None


class PullRequestSummary(BaseModel):
    pull_request_id: int
    number: int
    title: str
    body_text: str | None = None
    body_excerpt: str | None = None
    color: str
    url: str
    state: str
    base_ref: str
    head_ref: str
    base_sha: str | None = None
    head_sha: str
    labels: list[str]
    updated_at: datetime
    stored_at: datetime
    file_count: int
    additions: int
    deletions: int
    changes: int
    changed_files: list[ChangedFileSummary]


class PullRequestListResponse(BaseModel):
    repository: RepositorySummary
    pull_requests: list[PullRequestSummary]
    state: Literal["open", "closed", "all"]
    limit: int
    offset: int
    total: int


class AuthRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)

    @field_validator("user_id", "password")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank.")
        return value


class AuthUserResponse(BaseModel):
    id: int
    user_id: str
    created_at: datetime | None = None


class AuthResponse(BaseModel):
    user: AuthUserResponse


class LogoutResponse(BaseModel):
    message: str


class CommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must not be blank.")
        return value


class CommentResponse(BaseModel):
    id: int
    pull_request_id: int
    file_path_id: int
    author_user_id: int
    author_login_id: str
    body: str
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    comments: list[CommentResponse]


class AtlasResponse(BaseModel):
    canvas_layout: dict[str, Any]
    pr_overlay: dict[str, Any]


class AnalysisRunRequest(BaseModel):
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    pr_numbers: list[int] = Field(min_length=1)
    repo_root: Path | None = None
    codeql_db: Path | None = None
    codeql_results: Path | None = None
    project_role_map: Path | None = None
    validation_evidence: Path | None = None
    query_pack_version: str = DEFAULT_QUERY_PACK_VERSION
    codeql_query_profile: Literal["lite", "full"] = DEFAULT_CODEQL_QUERY_PROFILE
    skip_schema: bool = False
    use_llm: bool = True

    @field_validator("pr_numbers")
    @classmethod
    def validate_pr_numbers(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("pr_numbers must contain positive integers.")
        return values


class AnalysisOutputResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    canvas_layout: dict[str, Any]
    pr_overlay: dict[str, Any]
    risk_analysis: dict[str, Any]
    merge_recommendation: dict[str, Any]
    file_details: dict[str, Any]


class AnalysisProgressEvent(BaseModel):
    timestamp: datetime
    stage: str
    message: str
    status: str
    percent: int | None = None
    pr_number: int | None = None


class AnalysisJobStartResponse(BaseModel):
    job_id: str
    status: str
    owner: str
    repo: str
    pr_numbers: list[int]


class AnalysisJobStatusResponse(BaseModel):
    job_id: str
    status: str
    owner: str
    repo: str
    pr_numbers: list[int]
    current_step: str | None = None
    percent: int
    events: list[AnalysisProgressEvent]
    result: AnalysisOutputResponse | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
