from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_QUERY_PACK_VERSION = "pr-impact-v1"
DEFAULT_CODEQL_QUERY_PROFILE = "lite"
CODEQL_QUERY_PROFILES = ("lite", "full")


@dataclass(frozen=True)
class AnalysisRequest:
    owner: str
    repo: str
    pr_numbers: tuple[int, ...]
    database_url: str = ""
    repo_root: Path | None = None
    codeql_db: Path | None = None
    codeql_results: Path | None = None
    project_role_map: Path | None = None
    validation_evidence: Path | None = None
    output: Path | None = None
    query_pack_version: str = DEFAULT_QUERY_PACK_VERSION
    codeql_query_profile: str = DEFAULT_CODEQL_QUERY_PROFILE
    focus_file_path_id: int | None = None
    use_semantic_retrieval: bool = False
    use_llm: bool = False
    llm_model: str = "gpt-5.5"
    llm_timeout_seconds: float = 60.0
    create_schema: bool = True


@dataclass(frozen=True)
class PullRequestInfo:
    id: int
    number: int
    title: str
    url: str
    state: str
    base_ref: str
    head_ref: str
    base_sha: str | None
    head_sha: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class FileChangeInfo:
    id: int
    pull_request_id: int
    pr_number: int
    file_path_id: int
    path: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None


@dataclass(frozen=True)
class HunkInfo:
    id: int
    pr_file_id: int
    pull_request_id: int
    pr_number: int
    file_path_id: int
    path: str
    hunk_index: int
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    hunk_json: dict[str, Any]

    @property
    def new_end(self) -> int:
        return self.new_start + max(self.new_lines, 1)


@dataclass(frozen=True)
class SourceContext:
    repository_id: int
    repo_key: str
    owner: str
    repo: str
    pull_requests: tuple[PullRequestInfo, ...]
    file_changes: tuple[FileChangeInfo, ...]
    hunks: tuple[HunkInfo, ...]

    @property
    def selected_pr_ids(self) -> tuple[int, ...]:
        return tuple(pr.id for pr in self.pull_requests)

    @property
    def selected_pr_numbers(self) -> tuple[int, ...]:
        return tuple(pr.number for pr in self.pull_requests)

    @property
    def analysis_id(self) -> str:
        prs = "-".join(str(number) for number in self.selected_pr_numbers)
        return f"temporary-v1:repo-{self.repository_id}:prs-{prs}"

    @property
    def analyzed_commit_sha(self) -> str:
        head_shas = [pr.head_sha for pr in self.pull_requests if pr.head_sha]
        if len(head_shas) == 1:
            return head_shas[0]
        if head_shas:
            return "multi-pr:" + ",".join(sorted(head_shas))
        return "unknown"


@dataclass(frozen=True)
class RagDocument:
    document_id: str
    document_type: str
    repository_id: int
    pull_request_id: int | None
    file_path_id: int | None
    path: str | None
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeQLRawResult:
    query_id: str
    query_version: str
    path: str | None
    start_line: int | None
    end_line: int | None
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeQLChangeInput:
    pull_request_id: int
    file_path_id: int
    hunk_id: int | None
    symbol_key: str
    symbol_name: str
    symbol_kind: str
    change_type: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StaticImpactFindingInput:
    repository_id: int
    pull_request_id: int
    file_path_id: int
    finding_type: str
    start_symbol_key: str | None
    end_symbol_key: str | None
    impact_path: list[Any]
    affected_paths: list[Any]
    affected_roles: list[Any]
    related_tests: list[Any]
    confidence: float
    query_id: str
    query_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeQLSnapshotInfo:
    id: int | None
    repository_id: int
    commit_sha: str
    codeql_database_uri: str
    query_pack_version: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeQLEvidence:
    snapshot: CodeQLSnapshotInfo
    changes: tuple[CodeQLChangeInput, ...]
    findings: tuple[StaticImpactFindingInput, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectRole:
    role_id: str
    name: str
    criticality: str
    paths: tuple[str, ...] = ()
    public_api: tuple[str, ...] = ()
    entrypoints: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()
    risk_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectRoleMap:
    version: int
    roles: tuple[ProjectRole, ...]
    source_path: str | None = None
    is_default: bool = False


@dataclass(frozen=True)
class RoleMatch:
    role_id: str
    name: str
    criticality: str
    match_reason: str
    risk_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationSignal:
    signal_type: str
    target: str
    status: str | None = None
    value: Any | None = None
    source: str | None = None
    document_id: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class DeterministicFileRisk:
    file_path_id: int
    path: str
    related_prs: tuple[int, ...]
    score: int
    reasons: tuple[str, ...]
    categories: tuple[str, ...]
    conflict_points: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class RiskFileFinding:
    file_path_id: int
    path: str
    node_id: str
    score: int
    risk_level: str
    public_surface_level: str
    related_prs: tuple[int, ...]
    reasons: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    static_impact_paths: tuple[dict[str, Any], ...]
    affected_project_roles: tuple[RoleMatch, ...]
    validation_signals: tuple[ValidationSignal, ...]
    documentation_context: tuple[dict[str, Any], ...]
    uncertainty_signals: tuple[str, ...]
    codeql_queries: tuple[str, ...]
    conflict_points: tuple[dict[str, Any], ...] = ()
    change_intent: str = "unknown"


@dataclass(frozen=True)
class AnalysisState:
    request: AnalysisRequest
    source_context: SourceContext
    rag_documents: tuple[RagDocument, ...]
    codeql_evidence: CodeQLEvidence
    role_map: ProjectRoleMap
    validation_signals: tuple[ValidationSignal, ...]
    deterministic_findings: tuple[DeterministicFileRisk, ...]
    risk_findings: tuple[RiskFileFinding, ...]
    outputs: dict[str, Any]
    errors: tuple[str, ...] = ()
    langchain_documents: tuple[Any, ...] = ()
    llm_analysis: dict[str, Any] = field(default_factory=dict)
