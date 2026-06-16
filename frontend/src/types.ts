export type ApiHealth = {
  status: string;
  api_version: string;
  database_url_configured: boolean;
  codeql_available: boolean;
  codeql_path?: string | null;
  llm_configured: boolean;
  llm_model: string;
};

export type RepositorySummary = {
  id: number;
  repo_key: string;
  owner: string;
  name: string;
  pull_request_count: number;
  last_imported_at?: string | null;
  artifact_status?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RepositoryListResponse = {
  repositories: RepositorySummary[];
  limit: number;
  offset: number;
  total: number;
};

export type RepositoryImportRequest = {
  owner: string;
  repo: string;
  state?: "open" | "closed" | "all";
  page?: number;
  limit?: number;
};

export type RepositoryImportResponse = {
  repository: RepositorySummary;
  imported_pr_count: number;
  state: "open" | "closed" | "all";
  page: number;
  limit: number;
  message: string;
};

export type RepositoryDeleteResponse = {
  repository: {
    repo_key: string;
    owner: string;
    name: string;
  };
  removed_artifacts: string[];
  message: string;
};

export type AiAgentChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AiAgentState = {
  owner?: string | null;
  repo?: string | null;
  pr_limit?: number | null;
  pr_state?: "open" | "closed" | "all";
  page?: number;
  imported?: boolean;
  last_repository_key?: string | null;
};

export type AiAgentEvent = {
  type: string;
  tool_name: string;
  message: string;
  ok: boolean;
  data: Record<string, unknown>;
};

export type AiAgentMessageRequest = {
  message: string;
  history?: AiAgentChatMessage[];
  state?: AiAgentState;
};

export type AiAgentMessageResponse = {
  reply: string;
  status: "running" | "requires_input" | "completed" | "error" | string;
  state: AiAgentState;
  events: AiAgentEvent[];
  repository?: RepositorySummary | null;
  pull_requests: Array<Record<string, unknown>>;
};

export type ChangedFileSummary = {
  file_path_id: number;
  path: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  hunk_count?: number;
  patch_excerpt?: string | null;
};

export type PullRequestSummary = {
  pull_request_id: number;
  number: number;
  title: string;
  body_text?: string | null;
  body_excerpt?: string | null;
  color: string;
  url: string;
  state: string;
  base_ref: string;
  head_ref: string;
  base_sha?: string | null;
  head_sha: string;
  labels: string[];
  updated_at: string;
  stored_at: string;
  file_count: number;
  additions: number;
  deletions: number;
  changes: number;
  changed_files: ChangedFileSummary[];
};

export type PullRequestListResponse = {
  repository: RepositorySummary;
  pull_requests: PullRequestSummary[];
  state: "open" | "closed" | "all";
  limit: number;
  offset: number;
  total: number;
};

export type AuthUser = {
  id: number;
  user_id: string;
  created_at?: string | null;
};

export type AuthResponse = {
  user: AuthUser;
};

export type Comment = {
  id: number;
  pull_request_id: number;
  file_path_id: number;
  author_user_id: number;
  author_login_id: string;
  body: string;
  created_at: string;
  updated_at: string;
};

export type CommentListResponse = {
  comments: Comment[];
};

export type AtlasNode = {
  id: string;
  node_type: string;
  file_path_id?: number;
  path?: string;
  label: string;
  group?: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  criticality?: string;
  base_style?: Record<string, unknown>;
};

export type AtlasEdge = {
  id: string;
  edge_type: string;
  source: string;
  target: string;
  weight?: number;
  reason?: string;
};

export type CanvasLayout = {
  repository_id?: number;
  layout_version?: string;
  nodes: AtlasNode[];
  edges: AtlasEdge[];
};

export type PrOverlay = {
  repository_id?: number;
  selected_pr_ids?: number[];
  pull_requests: Array<{
    pull_request_id: number;
    number: number;
    title: string;
    color: string;
    files: ChangedFileSummary[];
  }>;
};

export type AtlasResponse = {
  canvas_layout: CanvasLayout;
  pr_overlay: PrOverlay;
};

export type RiskFile = {
  file_path_id: number;
  path: string;
  node_id: string;
  risk_level: "low" | "medium" | "high" | "critical" | string;
  score: number;
  public_surface_level?: string;
  change_intent?: string;
  related_prs?: number[];
  reasons?: string[];
  evidence?: Array<Record<string, unknown>>;
  static_impact_paths?: Array<Record<string, unknown>>;
  affected_project_roles?: Array<Record<string, unknown>>;
  validation_signals?: Array<Record<string, unknown>>;
  documentation_context?: Array<Record<string, unknown>>;
  uncertainty_signals?: string[];
  codeql_queries?: string[];
};

export type AnalysisOutput = {
  canvas_layout: CanvasLayout;
  pr_overlay: PrOverlay;
  risk_analysis: {
    analysis_id?: string;
    repository_id?: number;
    selected_pr_ids?: number[];
    summary?: string;
    risk_counts?: Record<string, number>;
    files: RiskFile[];
    errors?: string[];
    codeql?: {
      query_profile?: "lite" | "full";
      query_suite?: string | null;
      snapshot_status?: string;
      label?: string;
    };
  };
  merge_recommendation: {
    recommended_order?: Array<Record<string, unknown>>;
    blocking_files?: Array<Record<string, unknown>>;
    recommended_actions?: Array<Record<string, unknown>>;
    llm_summary?: string;
  };
  llm_analysis?: {
    enabled?: boolean;
    model?: string;
    summary?: string;
    report?: {
      change_intent?: string;
      review_focus?: string[];
      file_explanations?: Array<{
        file_path_id?: number | null;
        file_path?: string;
        explanation?: string;
        review_focus?: string[];
      }>;
      merge_notes?: string[];
    };
    reports?: Array<Record<string, unknown>>;
    errors?: string[];
  };
  file_details: Record<string, Record<string, unknown>>;
};

export type AnalysisSettings = {
  repo_root: string;
  codeql_db: string;
  codeql_results: string;
  project_role_map: string;
  validation_evidence: string;
  query_pack_version: string;
  codeql_query_profile: "lite" | "full";
  skip_schema: boolean;
};

export type AnalysisRunRequest = {
  owner: string;
  repo: string;
  pr_numbers: number[];
  repo_root?: string;
  codeql_db?: string;
  codeql_results?: string;
  project_role_map?: string;
  validation_evidence?: string;
  query_pack_version?: string;
  codeql_query_profile?: "lite" | "full";
  skip_schema?: boolean;
  use_llm?: boolean;
};

export type AnalysisProgressEvent = {
  timestamp: string;
  stage: string;
  message: string;
  status: string;
  percent?: number | null;
  pr_number?: number | null;
};

export type AnalysisJobStartResponse = {
  job_id: string;
  status: string;
  owner: string;
  repo: string;
  pr_numbers: number[];
};

export type AnalysisJobStatusResponse = {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  owner: string;
  repo: string;
  pr_numbers: number[];
  current_step?: string | null;
  percent: number;
  events: AnalysisProgressEvent[];
  result?: AnalysisOutput | null;
  error?: string | null;
  started_at: string;
  finished_at?: string | null;
};
