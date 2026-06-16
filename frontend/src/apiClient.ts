import type {
  AiAgentMessageRequest,
  AiAgentMessageResponse,
  AnalysisOutput,
  AnalysisJobStartResponse,
  AnalysisJobStatusResponse,
  AnalysisRunRequest,
  ApiHealth,
  AtlasResponse,
  AuthResponse,
  Comment,
  CommentListResponse,
  PullRequestListResponse,
  RepositoryDeleteResponse,
  RepositoryImportRequest,
  RepositoryImportResponse,
  RepositoryListResponse
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type BasicAuthCredentials = {
  userId: string;
  password: string;
};

let basicAuthCredentials: BasicAuthCredentials | null = null;

export function setBasicAuthCredentials(credentials: BasicAuthCredentials): void {
  basicAuthCredentials = credentials;
}

export function clearBasicAuthCredentials(): void {
  basicAuthCredentials = null;
}

export async function fetchHealth(): Promise<ApiHealth> {
  return request<ApiHealth>("/api/v1/health");
}

export async function fetchMe(): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/me");
}

export async function signup(user_id: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>(
    "/api/v1/auth/signup",
    jsonRequest("POST", { user_id, password }),
    { auth: false }
  );
}

export async function login(user_id: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>(
    "/api/v1/auth/login",
    jsonRequest("POST", { user_id, password }),
    { auth: false }
  );
}

export async function logout(): Promise<{ message: string }> {
  return request<{ message: string }>("/api/v1/auth/logout", { method: "POST" });
}

export async function fetchRepositories(params: {
  query?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<RepositoryListResponse> {
  return request<RepositoryListResponse>(`/api/v1/repositories${queryString(params)}`);
}

export async function createRepository(
  body: RepositoryImportRequest
): Promise<RepositoryImportResponse> {
  return request<RepositoryImportResponse>("/api/v1/repositories", jsonRequest("POST", body));
}

export async function refreshRepository(
  owner: string,
  repo: string,
  body: RepositoryImportRequest
): Promise<RepositoryImportResponse> {
  return request<RepositoryImportResponse>(
    `/api/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
    jsonRequest("PATCH", body)
  );
}

export async function deleteRepository(
  owner: string,
  repo: string
): Promise<RepositoryDeleteResponse> {
  return request<RepositoryDeleteResponse>(
    `/api/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
    { method: "DELETE" }
  );
}

export async function sendAiAgentMessage(
  body: AiAgentMessageRequest
): Promise<AiAgentMessageResponse> {
  return request<AiAgentMessageResponse>(
    "/api/v1/ai-agent/messages",
    jsonRequest("POST", body)
  );
}

export async function fetchPullRequests(
  owner: string,
  repo: string,
  params: {
    state?: "open" | "closed" | "all";
    query?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<PullRequestListResponse> {
  const search = queryString({
    state: params.state ?? "all",
    query: params.query,
    limit: params.limit,
    offset: params.offset
  });
  return request<PullRequestListResponse>(
    `/api/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pull-requests${search}`
  );
}

export async function fetchAtlas(
  owner: string,
  repo: string,
  prNumbers: number[]
): Promise<AtlasResponse> {
  const prs = prNumbers.join(",");
  return request<AtlasResponse>(
    `/api/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/atlas?prs=${encodeURIComponent(prs)}`
  );
}

export async function runAnalysis(body: AnalysisRunRequest): Promise<AnalysisOutput> {
  return request<AnalysisOutput>("/api/v1/analysis", jsonRequest("POST", body));
}

export async function startAnalysisJob(
  body: AnalysisRunRequest
): Promise<AnalysisJobStartResponse> {
  return request<AnalysisJobStartResponse>("/api/v1/analysis/jobs", jsonRequest("POST", body));
}

export async function fetchAnalysisJob(jobId: string): Promise<AnalysisJobStatusResponse> {
  return request<AnalysisJobStatusResponse>(
    `/api/v1/analysis/jobs/${encodeURIComponent(jobId)}`
  );
}

export async function fetchComments(
  owner: string,
  repo: string,
  prNumber: number,
  filePathId: number
): Promise<CommentListResponse> {
  return request<CommentListResponse>(
    `/api/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pull-requests/${prNumber}/files/${filePathId}/comments`
  );
}

export async function createComment(
  owner: string,
  repo: string,
  prNumber: number,
  filePathId: number,
  body: string
): Promise<Comment> {
  return request<Comment>(
    `/api/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pull-requests/${prNumber}/files/${filePathId}/comments`,
    jsonRequest("POST", { body })
  );
}

function jsonRequest(method: "POST" | "PATCH", body: unknown): RequestInit {
  return {
    method,
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  };
}

async function request<T>(
  path: string,
  init?: RequestInit,
  options: { auth?: boolean } = {}
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: requestHeaders(init?.headers, options.auth !== false)
    });
  } catch (error) {
    throw new ApiError(0, "FastAPI server is not reachable.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response));
  }
  return (await response.json()) as T;
}

function requestHeaders(headers: HeadersInit | undefined, withAuth: boolean): HeadersInit {
  const result = new Headers(headers);
  if (withAuth && basicAuthCredentials) {
    result.set(
      "Authorization",
      `Basic ${base64Utf8(`${basicAuthCredentials.userId}:${basicAuthCredentials.password}`)}`
    );
  }
  return Object.fromEntries(result.entries());
}

function base64Utf8(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}

async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail.map(String).join("; ");
    }
  } catch {
    return response.statusText || "Request failed.";
  }
  return response.statusText || "Request failed.";
}
