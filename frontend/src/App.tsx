import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  FileCode2,
  FolderTree,
  LogOut,
  Loader2,
  MessageSquare,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  Trash2,
  X,
  XCircle
} from "lucide-react";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  clearBasicAuthCredentials,
  createComment,
  createRepository,
  deleteRepository,
  fetchAtlas,
  fetchAnalysisJob,
  fetchComments,
  fetchHealth,
  fetchMe,
  fetchPullRequests,
  fetchRepositories,
  login,
  logout,
  refreshRepository,
  sendAiAgentMessage,
  setBasicAuthCredentials,
  startAnalysisJob,
  signup
} from "./apiClient";
import type {
  AiAgentChatMessage,
  AiAgentEvent,
  AiAgentState,
  AnalysisJobStatusResponse,
  AnalysisOutput,
  AnalysisRunRequest,
  ApiHealth,
  AtlasNode,
  AtlasResponse,
  ChangedFileSummary,
  AuthUser,
  Comment,
  PullRequestSummary,
  RepositoryImportRequest,
  RepositorySummary,
  RiskFile
} from "./types";

const PR_COLORS = [
  "#1d4ed8",
  "#dc2626",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#be123c",
  "#65a30d",
  "#c026d3",
  "#0f766e",
  "#92400e",
  "#475569"
];
const REPOSITORY_PAGE_SIZE = 12;
const PR_PAGE_SIZE = 8;

type SelectedFileInspector = {
  file_path_id: number;
  path: string;
  label: string;
  node_type: string;
  related_prs: Array<{
    pull_request_id: number;
    number: number;
    title: string;
    color: string;
    file: ChangedFileSummary;
  }>;
  risk: RiskFile | null;
  detail: Record<string, unknown> | null;
};

type OverlayFileMarker = {
  pull_request_id: number;
  number: number;
  title: string;
  color: string;
};

export default function App() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [repositoriesError, setRepositoriesError] = useState<ApiError | null>(null);
  const [repositoryActionError, setRepositoryActionError] = useState<ApiError | null>(null);
  const [repositoryQuery, setRepositoryQuery] = useState("");
  const [repositoryOffset, setRepositoryOffset] = useState(0);
  const [repositoryTotal, setRepositoryTotal] = useState(0);
  const [selectedRepository, setSelectedRepository] = useState<RepositorySummary | null>(null);
  const [pullRequests, setPullRequests] = useState<PullRequestSummary[]>([]);
  const [pullRequestsError, setPullRequestsError] = useState<ApiError | null>(null);
  const [pullRequestQuery, setPullRequestQuery] = useState("");
  const [pullRequestOffset, setPullRequestOffset] = useState(0);
  const [pullRequestTotal, setPullRequestTotal] = useState(0);
  const [selectedPrNumbers, setSelectedPrNumbers] = useState<number[]>([]);
  const [selectedPrByNumber, setSelectedPrByNumber] = useState<Record<number, PullRequestSummary>>({});
  const [atlas, setAtlas] = useState<AtlasResponse | null>(null);
  const [atlasError, setAtlasError] = useState<ApiError | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisOutput | null>(null);
  const [analysisError, setAnalysisError] = useState<ApiError | null>(null);
  const [analysisJob, setAnalysisJob] = useState<AnalysisJobStatusResponse | null>(null);
  const [activeAnalysisJobId, setActiveAnalysisJobId] = useState<string | null>(null);
  const [analysisPrSnapshot, setAnalysisPrSnapshot] = useState<PullRequestSummary[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [loading, setLoading] = useState({
    auth: true,
    health: true,
    repositories: true,
    pullRequests: false,
    atlas: false,
    analysis: false,
    repositoryAction: false
  });

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (currentUser) {
      void loadRepositories({ query: repositoryQuery, offset: repositoryOffset });
    }
  }, [currentUser]);

  useEffect(() => {
    if (!activeAnalysisJobId || !loading.analysis) {
      return;
    }
    let cancelled = false;
    async function poll() {
      if (!activeAnalysisJobId) {
        return;
      }
      try {
        const job = await fetchAnalysisJob(activeAnalysisJobId);
        if (cancelled) {
          return;
        }
        setAnalysisJob(job);
        if (job.status === "succeeded" && job.result) {
          setAnalysis(job.result);
          setAtlas({
            canvas_layout: job.result.canvas_layout,
            pr_overlay: job.result.pr_overlay
          });
          setSelectedFileId(job.result.risk_analysis.files[0]?.file_path_id ?? null);
          setActiveAnalysisJobId(null);
          setLoading((current) => ({ ...current, analysis: false }));
        } else if (job.status === "failed") {
          setAnalysisError(new ApiError(500, job.error || "분석이 실패했습니다."));
          setActiveAnalysisJobId(null);
          setLoading((current) => ({ ...current, analysis: false }));
        }
      } catch (error) {
        if (!cancelled) {
          const normalized = normalizeApiError(error);
          handleUnauthorized(normalized);
          setAnalysisError(normalized);
          setActiveAnalysisJobId(null);
          setLoading((current) => ({ ...current, analysis: false }));
        }
      }
    }
    void poll();
    const timer = window.setInterval(() => void poll(), 1200);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeAnalysisJobId, loading.analysis]);

  async function bootstrap() {
    setLoading((current) => ({ ...current, auth: true, health: true, repositories: false }));
    const [healthResult, authResult] = await Promise.allSettled([
      fetchHealth(),
      fetchMe()
    ]);

    if (healthResult.status === "fulfilled") {
      setHealth(healthResult.value);
      setHealthError(null);
    } else {
      setHealth(null);
      setHealthError(errorMessage(healthResult.reason));
    }

    if (authResult.status === "fulfilled") {
      setCurrentUser(authResult.value.user);
      setAuthError(null);
    } else {
      const error = normalizeApiError(authResult.reason);
      setCurrentUser(null);
      setAuthError(error.status === 401 ? null : error.detail);
      setRepositories([]);
      setRepositoriesError(null);
    }
    setLoading((current) => ({ ...current, auth: false, health: false }));
  }

  async function loadRepositories({
    query = repositoryQuery,
    offset = repositoryOffset
  }: {
    query?: string;
    offset?: number;
  } = {}) {
    if (!currentUser) {
      return;
    }
    setLoading((current) => ({ ...current, repositories: true }));
    try {
      const response = await fetchRepositories({
        query,
        offset,
        limit: REPOSITORY_PAGE_SIZE
      });
      setRepositories(response.repositories);
      setRepositoryTotal(response.total);
      setRepositoryQuery(query);
      setRepositoryOffset(offset);
      setRepositoriesError(null);
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setRepositories([]);
      setRepositoryTotal(0);
      setRepositoriesError(normalized);
    } finally {
      setLoading((current) => ({ ...current, repositories: false }));
    }
  }

  async function handleAuthSubmit(mode: "login" | "signup", userId: string, password: string) {
    setLoading((current) => ({ ...current, auth: true }));
    setAuthError(null);
    try {
      const response = mode === "login"
        ? await login(userId, password)
        : await signup(userId, password);
      setBasicAuthCredentials({ userId, password });
      setCurrentUser(response.user);
      setRepositoryQuery("");
      setRepositoryOffset(0);
      setSelectedRepository(null);
    } catch (error) {
      setAuthError(errorMessage(error));
    } finally {
      setLoading((current) => ({ ...current, auth: false }));
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Local logout still clears the app shell if the session is already gone.
    }
    clearAuthenticatedState();
  }

  async function selectRepository(repository: RepositorySummary) {
    setSelectedRepository(repository);
    setPullRequestQuery("");
    setPullRequestOffset(0);
    setPullRequestTotal(0);
    setPullRequests([]);
    setPullRequestsError(null);
    setSelectedPrNumbers([]);
    setSelectedPrByNumber({});
    setAtlas(null);
    setAnalysis(null);
    setAnalysisJob(null);
    setActiveAnalysisJobId(null);
    setAnalysisPrSnapshot([]);
    setSelectedFileId(null);
    await loadPullRequests(repository, { query: "", offset: 0 });
  }

  async function loadPullRequests(
    repository = selectedRepository,
    {
      query = pullRequestQuery,
      offset = pullRequestOffset
    }: {
      query?: string;
      offset?: number;
    } = {}
  ) {
    if (!repository) {
      return;
    }
    setLoading((current) => ({ ...current, pullRequests: true }));
    try {
      const response = await fetchPullRequests(repository.owner, repository.name, {
        state: "all",
        query,
        offset,
        limit: PR_PAGE_SIZE
      });
      setPullRequests(response.pull_requests);
      setSelectedPrByNumber((current) => {
        let changed = false;
        const next = { ...current };
        for (const pullRequest of response.pull_requests) {
          if (selectedPrNumbers.includes(pullRequest.number)) {
            next[pullRequest.number] = pullRequest;
            changed = true;
          }
        }
        return changed ? next : current;
      });
      setPullRequestTotal(response.total);
      setPullRequestQuery(query);
      setPullRequestOffset(offset);
      setPullRequestsError(null);
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setPullRequestsError(normalized);
    } finally {
      setLoading((current) => ({ ...current, pullRequests: false }));
    }
  }

  async function handleCreateRepository(request: RepositoryImportRequest) {
    setLoading((current) => ({ ...current, repositoryAction: true }));
    setRepositoryActionError(null);
    try {
      await createRepository(request);
      await loadRepositories({ query: repositoryQuery, offset: repositoryOffset });
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setRepositoryActionError(normalized);
    } finally {
      setLoading((current) => ({ ...current, repositoryAction: false }));
    }
  }

  async function handleRefreshRepository(repository: RepositorySummary) {
    setLoading((current) => ({ ...current, repositoryAction: true }));
    setRepositoryActionError(null);
    try {
      await refreshRepository(repository.owner, repository.name, {
        owner: repository.owner,
        repo: repository.name,
        state: "open",
        page: 1,
        limit: 30
      });
      await loadRepositories({ query: repositoryQuery, offset: repositoryOffset });
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setRepositoryActionError(normalized);
    } finally {
      setLoading((current) => ({ ...current, repositoryAction: false }));
    }
  }

  async function handleDeleteRepository(repository: RepositorySummary) {
    const confirmed = window.confirm(`${repository.owner}/${repository.name} 레포지토리와 캐시된 분석 산출물을 삭제할까요?`);
    if (!confirmed) {
      return;
    }
    setLoading((current) => ({ ...current, repositoryAction: true }));
    setRepositoryActionError(null);
    try {
      await deleteRepository(repository.owner, repository.name);
      setRepositories((current) => current.filter((item) => item.id !== repository.id));
      if (selectedRepository?.id === repository.id) {
        setSelectedRepository(null);
        setPullRequests([]);
        setSelectedPrNumbers([]);
        setSelectedPrByNumber({});
        setAtlas(null);
        setAnalysis(null);
        setAnalysisJob(null);
        setAnalysisPrSnapshot([]);
      }
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setRepositoryActionError(normalized);
    } finally {
      setLoading((current) => ({ ...current, repositoryAction: false }));
    }
  }

  async function togglePr(pullRequest: PullRequestSummary) {
    if (loading.analysis) {
      return;
    }
    const number = pullRequest.number;
    const next = selectedPrNumbers.includes(number)
      ? selectedPrNumbers.filter((item) => item !== number)
      : [...selectedPrNumbers, number].sort((left, right) => left - right);
    setSelectedPrNumbers(next);
    setSelectedPrByNumber((current) => {
      const updated = { ...current };
      if (next.includes(number)) {
        updated[number] = pullRequest;
      } else {
        delete updated[number];
      }
      return updated;
    });
    setAnalysis(null);
    setAnalysisJob(null);
    setAnalysisPrSnapshot([]);
    setSelectedFileId(null);
    if (!selectedRepository || next.length === 0) {
      setAtlas(null);
      return;
    }
    setLoading((current) => ({ ...current, atlas: true }));
    setAtlasError(null);
    try {
      const response = await fetchAtlas(selectedRepository.owner, selectedRepository.name, next);
      setAtlas(response);
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setAtlas(null);
      setAtlasError(normalized);
    } finally {
      setLoading((current) => ({ ...current, atlas: false }));
    }
  }

  async function analyzeSelectedPrs() {
    if (!selectedRepository || selectedPrNumbers.length === 0) {
      return;
    }
    if (!health?.llm_configured) {
      setAnalysisError(new ApiError(503, "OPENAI_API_KEY is required for LLM analysis."));
      return;
    }
    const snapshot = selectedPrNumbers
      .map((number) => selectedPrByNumber[number])
      .filter((pullRequest): pullRequest is PullRequestSummary => Boolean(pullRequest));
    setLoading((current) => ({ ...current, analysis: true }));
    setAnalysisError(null);
    setAnalysis(null);
    setSelectedFileId(null);
    setAnalysisPrSnapshot(snapshot);
    try {
      const started = await startAnalysisJob(buildAnalysisRequest(selectedRepository, selectedPrNumbers));
      setActiveAnalysisJobId(started.job_id);
      setAnalysisJob({
        ...started,
        current_step: "분석 job이 시작되었습니다.",
        percent: 0,
        events: [],
        result: null,
        error: null,
        started_at: new Date().toISOString(),
        finished_at: null
      });
    } catch (error) {
      const normalized = normalizeApiError(error);
      handleUnauthorized(normalized);
      setAnalysisError(normalized);
      setLoading((current) => ({ ...current, analysis: false }));
    }
  }

  function handleUnauthorized(error: ApiError) {
    if (error.status === 401) {
      clearAuthenticatedState();
    }
  }

  function clearAuthenticatedState() {
    clearBasicAuthCredentials();
    setCurrentUser(null);
    setRepositories([]);
    setRepositoryTotal(0);
    setSelectedRepository(null);
    setPullRequests([]);
    setSelectedPrNumbers([]);
    setSelectedPrByNumber({});
    setAtlas(null);
    setAnalysis(null);
    setAnalysisJob(null);
    setActiveAnalysisJobId(null);
    setAnalysisPrSnapshot([]);
    setSelectedFileId(null);
  }

  const activeCanvas = analysis?.canvas_layout ?? atlas?.canvas_layout ?? null;
  const activeOverlay = analysis?.pr_overlay ?? atlas?.pr_overlay ?? null;
  const riskFiles = analysis?.risk_analysis.files ?? [];
  const selectedFileDetail =
    selectedFileId == null ? null : analysis?.file_details[String(selectedFileId)] ?? null;
  const selectedFileInspector = buildSelectedFileInspector({
    selectedFileId,
    canvas: activeCanvas,
    overlay: activeOverlay,
    riskFiles,
    detail: selectedFileDetail
  });
  const selectedPullRequests = selectedPrNumbers
    .map((number) => selectedPrByNumber[number])
    .filter((pullRequest): pullRequest is PullRequestSummary => Boolean(pullRequest));
  const displayedPrSnapshot = loading.analysis && analysisPrSnapshot.length > 0
    ? analysisPrSnapshot
    : selectedPullRequests;

  return (
    <main className="appShell">
      <header className="topBar">
        <div>
          <p className="eyebrow">PR 충돌 아틀라스</p>
          <h1>경로 아틀라스</h1>
        </div>
        <div className="topActions">
          {currentUser ? (
            <span className="userBadge">{currentUser.user_id}</span>
          ) : null}
          {currentUser ? (
            <button className="textButton" type="button" onClick={handleLogout}>
              <LogOut size={16} />
              로그아웃
            </button>
          ) : null}
          <button className="iconButton" type="button" onClick={bootstrap} aria-label="새로고침">
            <RefreshCw size={18} />
          </button>
        </div>
      </header>

      <StatusStrip
        health={health}
        healthError={healthError}
        repositoriesError={repositoriesError}
        loading={loading.health || loading.auth}
      />

      {!currentUser ? (
        <AuthScreen
          loading={loading.auth}
          error={authError}
          onSubmit={handleAuthSubmit}
        />
      ) : !selectedRepository ? (
        <RepositoryBoard
          repositories={repositories}
          loading={loading.repositories}
          actionLoading={loading.repositoryAction}
          error={repositoriesError}
          actionError={repositoryActionError}
          query={repositoryQuery}
          limit={REPOSITORY_PAGE_SIZE}
          offset={repositoryOffset}
          total={repositoryTotal}
          onCreate={handleCreateRepository}
          onRefresh={handleRefreshRepository}
          onDelete={handleDeleteRepository}
          llmConfigured={Boolean(health?.llm_configured)}
          onAgentImported={() => loadRepositories({ query: repositoryQuery, offset: repositoryOffset })}
          onSearch={(query) => void loadRepositories({ query, offset: 0 })}
          onPage={(offset) => void loadRepositories({ query: repositoryQuery, offset })}
          onSelect={selectRepository}
        />
      ) : (
        <section className="workspace">
          <PrSidebar
            repository={selectedRepository}
            pullRequests={pullRequests}
            selectedPrNumbers={selectedPrNumbers}
            disabled={loading.analysis}
            loading={loading.pullRequests}
            error={pullRequestsError}
            query={pullRequestQuery}
            limit={PR_PAGE_SIZE}
            offset={pullRequestOffset}
            total={pullRequestTotal}
            onBack={() => setSelectedRepository(null)}
            onSearch={(query) => void loadPullRequests(selectedRepository, { query, offset: 0 })}
            onPage={(offset) => void loadPullRequests(selectedRepository, { query: pullRequestQuery, offset })}
            onToggle={togglePr}
          />
          <PathAtlasCanvas
            canvas={activeCanvas}
            overlay={activeOverlay}
            riskFiles={riskFiles}
            loading={loading.atlas}
            error={atlasError}
            selectedFileId={selectedFileId}
            onSelectFile={setSelectedFileId}
          />
          <AnalysisPanel
            repository={selectedRepository}
            selectedPrNumbers={selectedPrNumbers}
            selectedPullRequests={displayedPrSnapshot}
            disabled={selectedPrNumbers.length === 0 || !health?.llm_configured}
            llmConfigured={Boolean(health?.llm_configured)}
            llmModel={health?.llm_model ?? ""}
            loading={loading.analysis}
            job={analysisJob}
            analysis={analysis}
            error={analysisError}
            selectedFileId={selectedFileId}
            selectedFile={selectedFileInspector}
            currentUser={currentUser}
            onAnalyze={analyzeSelectedPrs}
            onSelectFile={setSelectedFileId}
          />
        </section>
      )}
    </main>
  );
}

function StatusStrip({
  health,
  healthError,
  repositoriesError,
  loading
}: {
  health: ApiHealth | null;
  healthError: string | null;
  repositoriesError: ApiError | null;
  loading: boolean;
}) {
  const state = healthError
    ? { className: "statusError", icon: <XCircle size={16} />, text: "FastAPI 서버에 연결할 수 없습니다." }
    : repositoriesError?.status === 503
      ? { className: "statusWarning", icon: <AlertTriangle size={16} />, text: "Postgres 접속 또는 인증 정보를 확인해야 합니다." }
      : health?.database_url_configured === false
        ? { className: "statusWarning", icon: <AlertTriangle size={16} />, text: "DATABASE_URL이 설정되지 않았습니다." }
        : { className: "statusOk", icon: <CheckCircle2 size={16} />, text: "API 연결됨" };

  return (
    <section className={`statusStrip ${state.className}`} aria-live="polite">
      <div className="statusMain">
        {loading ? <Loader2 className="spin" size={16} /> : state.icon}
        <span>{loading ? "API 상태 확인 중..." : state.text}</span>
      </div>
      <div className="statusMeta">
        <Server size={15} />
        <span>CodeQL {health?.codeql_available ? "사용 가능" : "감지 안 됨"}</span>
        <span>LLM {health?.llm_configured ? health.llm_model : "키 없음"}</span>
      </div>
    </section>
  );
}

function AuthScreen({
  loading,
  error,
  onSubmit
}: {
  loading: boolean;
  error: string | null;
  onSubmit: (mode: "login" | "signup", userId: string, password: string) => Promise<void>;
}) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(mode, userId, password);
  }

  return (
    <section className="authShell">
      <form className="authPanel" onSubmit={submit}>
        <div>
          <p className="eyebrow">계정</p>
          <h2>{mode === "login" ? "로그인" : "회원가입"}</h2>
        </div>
        <div className="authMode">
          <button
            className={mode === "login" ? "selected" : ""}
            type="button"
            onClick={() => setMode("login")}
          >
            로그인
          </button>
          <button
            className={mode === "signup" ? "selected" : ""}
            type="button"
            onClick={() => setMode("signup")}
          >
            회원가입
          </button>
        </div>
        <label>
          <span>아이디</span>
          <input
            autoFocus
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
          />
        </label>
        <label>
          <span>비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <InlineNotice text={error} tone="warning" /> : null}
        <button
          className="primaryButton"
          disabled={loading || !userId.trim() || !password.trim()}
          type="submit"
        >
          {loading ? <Loader2 className="spin" size={16} /> : null}
          {mode === "login" ? "로그인하기" : "계정 만들기"}
        </button>
      </form>
    </section>
  );
}

function RepositoryBoard({
  repositories,
  loading,
  actionLoading,
  error,
  actionError,
  query,
  limit,
  offset,
  total,
  onCreate,
  onRefresh,
  onDelete,
  llmConfigured,
  onAgentImported,
  onSearch,
  onPage,
  onSelect
}: {
  repositories: RepositorySummary[];
  loading: boolean;
  actionLoading: boolean;
  error: ApiError | null;
  actionError: ApiError | null;
  query: string;
  limit: number;
  offset: number;
  total: number;
  onCreate: (request: RepositoryImportRequest) => Promise<void>;
  onRefresh: (repository: RepositorySummary) => Promise<void>;
  onDelete: (repository: RepositorySummary) => Promise<void>;
  llmConfigured: boolean;
  onAgentImported: () => Promise<void>;
  onSearch: (query: string) => void;
  onPage: (offset: number) => void;
  onSelect: (repository: RepositorySummary) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [searchText, setSearchText] = useState(query);
  const [form, setForm] = useState<Required<RepositoryImportRequest>>({
    owner: "",
    repo: "",
    state: "open",
    page: 1,
    limit: 30
  });

  useEffect(() => {
    setSearchText(query);
  }, [query]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.owner.trim() || !form.repo.trim()) {
      return;
    }
    await onCreate({
      owner: form.owner.trim(),
      repo: form.repo.trim(),
      state: form.state,
      page: form.page,
      limit: form.limit
    });
    setAdding(false);
    setForm({ owner: "", repo: "", state: "open", page: 1, limit: 30 });
  }

  return (
    <section className="board">
      <div className="sectionHeader">
        <div>
          <h2>레포지토리</h2>
          <p>가져온 레포지토리 {total}개</p>
        </div>
        <button className="primaryButton" type="button" onClick={() => setAdding(true)}>
          <Plus size={16} />
          레포지토리 추가
        </button>
      </div>
      <form
        className="listToolbar"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch(searchText.trim());
        }}
      >
        <label>
          <Search size={16} />
          <input
            placeholder="레포지토리 검색"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
        </label>
        <button className="textButton" type="submit">
          검색
        </button>
        {query ? (
          <button
            className="textButton"
            type="button"
            onClick={() => {
              setSearchText("");
              onSearch("");
            }}
          >
            지우기
          </button>
        ) : null}
      </form>
      <AiAgentPanel
        llmConfigured={llmConfigured}
        onImported={onAgentImported}
      />
      {adding ? (
        <div className="modalBackdrop">
          <form className="repoDialog" onSubmit={submit}>
            <div className="dialogHeader">
              <div>
                <h3>레포지토리 추가</h3>
                <p>공개 GitHub PR 데이터를 가져옵니다</p>
              </div>
              <button className="iconButton" type="button" onClick={() => setAdding(false)} aria-label="닫기">
                <X size={16} />
              </button>
            </div>
            <div className="repoFormGrid">
              <label>
                <span>소유자</span>
                <input
                  autoFocus
                  value={form.owner}
                  onChange={(event) => setForm({ ...form, owner: event.target.value })}
                />
              </label>
              <label>
                <span>레포</span>
                <input
                  value={form.repo}
                  onChange={(event) => setForm({ ...form, repo: event.target.value })}
                />
              </label>
              <label>
                <span>상태</span>
                <select
                  value={form.state}
                  onChange={(event) => setForm({ ...form, state: event.target.value as Required<RepositoryImportRequest>["state"] })}
                >
                  <option value="open">열림</option>
                  <option value="closed">닫힘</option>
                  <option value="all">전체</option>
                </select>
              </label>
              <label>
                <span>가져올 PR 수</span>
                <input
                  max={100}
                  min={1}
                  type="number"
                  value={form.limit}
                  onChange={(event) => setForm({ ...form, limit: Number(event.target.value) })}
                />
              </label>
            </div>
            <div className="dialogActions">
              <button className="textButton" type="button" onClick={() => setAdding(false)}>
                취소
              </button>
              <button className="primaryButton" disabled={actionLoading} type="submit">
                {actionLoading ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
                가져오기
              </button>
            </div>
          </form>
        </div>
      ) : null}
      {loading ? <LoadingBlock label="레포지토리 불러오는 중" /> : null}
      {error ? <EmptyState title="레포지토리 데이터를 불러올 수 없습니다" text={errorMessage(error)} /> : null}
      {actionError ? <EmptyState title="레포지토리 작업 실패" text={errorMessage(actionError)} /> : null}
      {!loading && !error && repositories.length === 0 ? (
        <EmptyState title="가져온 레포지토리가 없습니다" text="공개 GitHub 레포지토리를 추가해 PR 데이터를 가져오세요." />
      ) : null}
      <div className="repositoryGrid">
        {repositories.map((repository) => (
          <article
            className="repositoryTile"
            key={repository.id}
          >
            <button className="repositoryOpen" type="button" onClick={() => onSelect(repository)}>
              <FolderTree size={18} />
              <span>
                <span className="repositoryName">{repository.owner}/{repository.name}</span>
                <span className="muted">PR {repository.pull_request_count}개</span>
              </span>
            </button>
            <div className="repoActions">
              <button
                className="iconButton"
                disabled={actionLoading}
                type="button"
                onClick={() => void onRefresh(repository)}
                aria-label={`${repository.owner}/${repository.name} 새로고침`}
              >
                <RefreshCw size={16} />
              </button>
              <button
                className="iconButton danger"
                disabled={actionLoading}
                type="button"
                onClick={() => void onDelete(repository)}
                aria-label={`${repository.owner}/${repository.name} 삭제`}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </article>
        ))}
      </div>
      <Pagination
        limit={limit}
        offset={offset}
        total={total}
        onPage={onPage}
      />
    </section>
  );
}

function AiAgentPanel({
  llmConfigured,
  onImported
}: {
  llmConfigured: boolean;
  onImported: () => Promise<void>;
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<AiAgentChatMessage[]>([]);
  const [agentState, setAgentState] = useState<AiAgentState>({});
  const [events, setEvents] = useState<AiAgentEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || loading || !llmConfigured) {
      return;
    }
    const userMessage: AiAgentChatMessage = { role: "user", content };
    const nextMessages = [...messages, userMessage].slice(-12);
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const response = await sendAiAgentMessage({
        message: content,
        history: messages.slice(-10),
        state: agentState
      });
      const assistantMessage: AiAgentChatMessage = {
        role: "assistant",
        content: response.reply
      };
      setMessages([...nextMessages, assistantMessage].slice(-12));
      setAgentState(response.state);
      setEvents(response.events);
      if (response.repository || response.events.some((item) => item.tool_name === "import_repository" && item.ok)) {
        await onImported();
      }
    } catch (err) {
      setError(normalizeApiError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="aiAgentPanel">
      <div className="aiAgentHeader">
        <div>
          <h3>AI agent</h3>
          <p>OpenAI 도구 판단</p>
        </div>
        <span className={llmConfigured ? "agentStatus ready" : "agentStatus blocked"}>
          {llmConfigured ? "ready" : "key required"}
        </span>
      </div>
      {!llmConfigured ? (
        <InlineNotice text="OPENAI_API_KEY가 필요합니다." tone="warning" />
      ) : null}
      <div className="agentMessages" aria-live="polite">
        {messages.length === 0 ? (
          <p className="muted">GitHub repository</p>
        ) : null}
        {messages.map((message, index) => (
          <div className={`agentBubble ${message.role}`} key={`${message.role}:${index}`}>
            {message.content}
          </div>
        ))}
      </div>
      {events.length > 0 ? (
        <ol className="agentEvents">
          {events.slice(-4).map((event, index) => (
            <li key={`${event.type}:${event.tool_name}:${index}`}>
              <span>{agentEventLabel(event)}</span>
              <small>{event.ok ? "ok" : "failed"}</small>
            </li>
          ))}
        </ol>
      ) : null}
      {error ? <InlineNotice text={errorMessage(error)} tone="warning" /> : null}
      <form className="agentInput" onSubmit={submit}>
        <input
          placeholder="https://github.com/owner/repo"
          value={input}
          onChange={(event) => setInput(event.target.value)}
        />
        <button
          className="primaryButton"
          disabled={!llmConfigured || loading || !input.trim()}
          type="submit"
        >
          {loading ? <Loader2 className="spin" size={16} /> : <MessageSquare size={16} />}
          보내기
        </button>
      </form>
    </section>
  );
}

function agentEventLabel(event: AiAgentEvent): string {
  if (event.type === "openai_decision") {
    return `OpenAI: ${event.tool_name}`;
  }
  return `Tool: ${event.tool_name}`;
}

function Pagination({
  limit,
  offset,
  total,
  onPage,
  disabled = false
}: {
  limit: number;
  offset: number;
  total: number;
  onPage: (offset: number) => void;
  disabled?: boolean;
}) {
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);
  return (
    <div className="pagination">
      <span>{start}-{end} / {total}</span>
      <div>
        <button
          className="iconButton"
          disabled={disabled || offset <= 0}
          type="button"
          onClick={() => onPage(Math.max(0, offset - limit))}
          aria-label="이전 페이지"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          className="iconButton"
          disabled={disabled || offset + limit >= total}
          type="button"
          onClick={() => onPage(offset + limit)}
          aria-label="다음 페이지"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

function PrSidebar({
  repository,
  pullRequests,
  selectedPrNumbers,
  disabled,
  loading,
  error,
  query,
  limit,
  offset,
  total,
  onBack,
  onSearch,
  onPage,
  onToggle
}: {
  repository: RepositorySummary;
  pullRequests: PullRequestSummary[];
  selectedPrNumbers: number[];
  disabled: boolean;
  loading: boolean;
  error: ApiError | null;
  query: string;
  limit: number;
  offset: number;
  total: number;
  onBack: () => void;
  onSearch: (query: string) => void;
  onPage: (offset: number) => void;
  onToggle: (pullRequest: PullRequestSummary) => void;
}) {
  const [searchText, setSearchText] = useState(query);

  useEffect(() => {
    setSearchText(query);
  }, [query]);

  return (
    <aside className="sidebar">
      <button className="textButton" disabled={disabled} type="button" onClick={onBack}>
        레포지토리
      </button>
      <div className="sidebarTitle">
        <h2>{repository.name}</h2>
        <p>{repository.owner} · 선택 {selectedPrNumbers.length}개</p>
      </div>
      <form
        className="sidebarSearch"
        onSubmit={(event) => {
          event.preventDefault();
          if (disabled) {
            return;
          }
          onSearch(searchText.trim());
        }}
      >
        <label>
          <Search size={15} />
          <input
            disabled={disabled}
            placeholder="PR 검색"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
        </label>
        <div>
          <button className="textButton" disabled={disabled} type="submit">검색</button>
          {query ? (
            <button
              className="textButton"
              disabled={disabled}
              type="button"
              onClick={() => {
                setSearchText("");
                onSearch("");
              }}
            >
              지우기
            </button>
          ) : null}
        </div>
      </form>
      {loading ? <LoadingBlock label="PR 불러오는 중" /> : null}
      {error ? <EmptyState title="PR 데이터를 불러올 수 없습니다" text={errorMessage(error)} /> : null}
      <div className="prList">
        {pullRequests.map((pullRequest) => {
          const checked = selectedPrNumbers.includes(pullRequest.number);
          const selectedIndex = selectedPrNumbers.indexOf(pullRequest.number);
          const color = checked && selectedIndex >= 0
            ? colorForPrIndex(selectedIndex)
            : pullRequest.color || colorForPrNumber(pullRequest.number);
          return (
            <label
              className={`prItem ${checked ? "selected" : ""}`}
              key={pullRequest.pull_request_id}
              style={{ "--pr-color": color } as CSSProperties}
            >
              <input
                checked={checked}
                disabled={disabled}
                type="checkbox"
                onChange={() => onToggle(pullRequest)}
              />
              <span className="prColor" style={{ backgroundColor: color }} />
              <span className="prContent">
                <span className="prTitle">#{pullRequest.number} {pullRequest.title}</span>
                <span className="muted">파일 {pullRequest.file_count}개, +{pullRequest.additions} -{pullRequest.deletions}</span>
              </span>
            </label>
          );
        })}
      </div>
      <Pagination
        disabled={disabled}
        limit={limit}
        offset={offset}
        total={total}
        onPage={onPage}
      />
    </aside>
  );
}

function PathAtlasCanvas({
  canvas,
  overlay,
  riskFiles,
  loading,
  error,
  selectedFileId,
  onSelectFile
}: {
  canvas: AtlasResponse["canvas_layout"] | null;
  overlay: AtlasResponse["pr_overlay"] | null;
  riskFiles: RiskFile[];
  loading: boolean;
  error: ApiError | null;
  selectedFileId: number | null;
  onSelectFile: (fileId: number) => void;
}) {
  const positionedNodes = useMemo(() => positionNodes(canvas?.nodes ?? []), [canvas]);
  const nodeById = useMemo(
    () => new Map(positionedNodes.map((node) => [node.id, node])),
    [positionedNodes]
  );
  const riskByFileId = useMemo(
    () => new Map(riskFiles.map((file) => [file.file_path_id, file])),
    [riskFiles]
  );
  const overlayByFileId = useMemo(() => overlayFileGroups(overlay), [overlay]);
  const bounds = useMemo(() => canvasBounds(positionedNodes), [positionedNodes]);

  return (
    <section className="canvasPane">
      <div className="canvasHeader">
        <div>
          <h2>경로 아틀라스</h2>
          <p>노드 {positionedNodes.length}개</p>
        </div>
        {loading ? <Loader2 className="spin" size={18} /> : null}
      </div>
      {(overlay?.pull_requests.length ?? 0) > 0 ? (
        <div className="prLegend" aria-label="선택한 PR 색상">
          {overlay?.pull_requests.map((pullRequest) => (
            <span className="legendChip" key={pullRequest.pull_request_id} title={pullRequest.title}>
              <span className="legendSwatch" style={{ backgroundColor: pullRequest.color }} />
              #{pullRequest.number}
            </span>
          ))}
        </div>
      ) : null}
      {error ? <EmptyState title="아틀라스를 불러올 수 없습니다" text={errorMessage(error)} /> : null}
      {!error && positionedNodes.length === 0 ? (
        <EmptyState title="PR을 선택하세요" text="왼쪽 목록에서 하나 이상의 PR을 선택하세요." />
      ) : (
        <svg className="atlasSvg" viewBox={bounds} role="img" aria-label="경로 아틀라스 캔버스">
          <g className="edgeLayer">
            {(canvas?.edges ?? []).map((edge) => {
              const source = nodeById.get(edge.source);
              const target = nodeById.get(edge.target);
              if (!source || !target) {
                return null;
              }
              return (
                <line
                  key={edge.id}
                  x1={(source.x ?? 0) + (source.width ?? 120) / 2}
                  y1={(source.y ?? 0) + (source.height ?? 32) / 2}
                  x2={(target.x ?? 0) + (target.width ?? 120) / 2}
                  y2={(target.y ?? 0) + (target.height ?? 32) / 2}
                />
              );
            })}
          </g>
          <g className="nodeLayer">
            {positionedNodes.map((node) => {
              const fileId = node.file_path_id;
              const risk = fileId == null ? undefined : riskByFileId.get(fileId);
              const overlayEntries = fileId == null ? [] : overlayByFileId.get(fileId) ?? [];
              const overlayColor = overlayEntries[0]?.color;
              const visibleMarkers = overlayEntries.slice(0, 4);
              const markerTextOffset = visibleMarkers.length > 0 ? 20 + visibleMarkers.length * 9 : 0;
              const isOverlap = overlayEntries.length > 1;
              const selected = fileId != null && fileId === selectedFileId;
              const nodeLabel = compactNodeLabel(node);
              const labelX = (node.x ?? 0) + 10 + markerTextOffset;
              const labelY = (node.y ?? 0) + 5;
              const labelWidth = Math.max(30, (node.width ?? 120) - (labelX - (node.x ?? 0)) - (risk ? 28 : 8));
              const labelHeight = Math.max(20, (node.height ?? 34) - 10);
              return (
                <g
                  className={`atlasNode ${risk ? `risk-${risk.risk_level}` : ""} ${selected ? "active" : ""} ${isOverlap ? "overlap" : ""}`}
                  key={node.id}
                  onClick={() => fileId != null && onSelectFile(fileId)}
                  onKeyDown={(event) => {
                    if (fileId != null && (event.key === "Enter" || event.key === " ")) {
                      onSelectFile(fileId);
                    }
                  }}
                  role={fileId != null ? "button" : undefined}
                  tabIndex={fileId != null ? 0 : -1}
                  data-node-id={node.id}
                  data-x={node.x}
                  data-y={node.y}
                >
                  <title>{node.path ?? node.label}</title>
                  <rect
                    x={node.x}
                    y={node.y}
                    width={node.width}
                    height={node.height}
                    rx="6"
                    style={{ stroke: isOverlap ? "#111827" : overlayColor ?? undefined }}
                  />
                  {visibleMarkers.map((entry, index) => (
                    <circle
                      className="overlayMarker"
                      cx={(node.x ?? 0) + 11 + index * 9}
                      cy={(node.y ?? 0) + 16}
                      fill={entry.color}
                      key={`${entry.pull_request_id}:${node.id}`}
                      r="4"
                    >
                      <title>PR #{entry.number} {entry.title}</title>
                    </circle>
                  ))}
                  {overlayEntries.length > visibleMarkers.length ? (
                    <text className="overlayCount" x={(node.x ?? 0) + 50} y={(node.y ?? 0) + 20}>
                      +{overlayEntries.length - visibleMarkers.length}
                    </text>
                  ) : null}
                  {risk ? (
                    <AlertTriangle
                      className="riskIcon"
                      size={14}
                      x={(node.x ?? 0) + (node.width ?? 120) - 20}
                      y={(node.y ?? 0) + 9}
                    />
                  ) : null}
                  <foreignObject
                    height={labelHeight}
                    width={labelWidth}
                    x={labelX}
                    y={labelY}
                  >
                    <div className="nodeLabelBox" title={node.path ?? node.label}>
                      {nodeLabel}
                    </div>
                  </foreignObject>
                </g>
              );
            })}
          </g>
        </svg>
      )}
    </section>
  );
}

function AnalysisPanel({
  repository,
  selectedPrNumbers,
  selectedPullRequests,
  disabled,
  llmConfigured,
  llmModel,
  loading,
  job,
  analysis,
  error,
  selectedFileId,
  selectedFile,
  currentUser,
  onAnalyze,
  onSelectFile
}: {
  repository: RepositorySummary;
  selectedPrNumbers: number[];
  selectedPullRequests: PullRequestSummary[];
  disabled: boolean;
  llmConfigured: boolean;
  llmModel: string;
  loading: boolean;
  job: AnalysisJobStatusResponse | null;
  analysis: AnalysisOutput | null;
  error: ApiError | null;
  selectedFileId: number | null;
  selectedFile: SelectedFileInspector | null;
  currentUser: AuthUser;
  onAnalyze: () => void;
  onSelectFile: (fileId: number) => void;
}) {
  return (
    <aside className="analysisPanel">
      <div className="panelHeader">
        <div>
          <h2>분석</h2>
          <p>{repository.owner}/{repository.name}</p>
        </div>
        <button
          className="primaryButton"
          disabled={disabled || loading}
          type="button"
          onClick={onAnalyze}
        >
          {loading ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
          분석 실행
        </button>
      </div>
      {selectedPrNumbers.length === 0 ? (
        <InlineNotice text="분석할 PR을 하나 이상 선택하세요." />
      ) : null}
      {!llmConfigured ? (
        <InlineNotice text="OpenAI API 키가 필요합니다. 서버 .env 또는 Docker env에 OPENAI_API_KEY를 설정하세요." tone="warning" />
      ) : (
        <InlineNotice text={`LLM 설명 생성 모델: ${llmModel}`} />
      )}
      {selectedPrNumbers.length === 1 ? (
        <InlineNotice text="선택한 PR이 base에 반영될 때의 영향 후보를 분석합니다." />
      ) : null}
      {selectedPrNumbers.length > 1 ? (
        <InlineNotice text="base 영향 후보와 선택 PR 간 겹침/근접 관계를 함께 분석합니다." />
      ) : null}
      {error ? <EmptyState title="분석 실패" text={errorMessage(error)} /> : null}
      {job && loading ? (
        <AnalysisProgress job={job} selectedPullRequests={selectedPullRequests} />
      ) : null}
      {selectedFile ? (
        <SelectedFilePanel
          currentUser={currentUser}
          file={selectedFile}
          repository={repository}
        />
      ) : (
        <SelectedPrPanel
          pullRequests={selectedPullRequests}
          onSelectFile={onSelectFile}
        />
      )}
      {analysis ? (
        <>
          <section className="analysisSummary">
            <h3>위험 요약</h3>
            {analysis.risk_analysis.codeql?.label ? (
              <p className="muted">{analysis.risk_analysis.codeql.label}</p>
            ) : null}
            <p>{analysis.risk_analysis.summary ?? "요약이 없습니다."}</p>
            {(analysis.risk_analysis.errors ?? []).map((item) => (
              <InlineNotice key={item} text={item} tone="warning" />
            ))}
          </section>
          <section className="riskList">
            <h3>위험 파일</h3>
            {analysis.risk_analysis.files.length === 0 ? (
              <p className="muted">위험 파일이 없습니다.</p>
            ) : null}
            {analysis.risk_analysis.files.map((file) => (
              <button
                className={`riskItem ${selectedFileId === file.file_path_id ? "selected" : ""}`}
                key={file.file_path_id}
                type="button"
                onClick={() => onSelectFile(file.file_path_id)}
              >
                <FileCode2 size={16} />
                <span>
                  <strong>{file.path}</strong>
                  <small>{riskLevelLabel(file.risk_level)} · 점수 {file.score}</small>
                </span>
              </button>
            ))}
          </section>
          <section className="mergeBox">
            <h3>병합 추천</h3>
            {(analysis.merge_recommendation.recommended_actions ?? []).slice(0, 4).map((item, index) => (
              <p key={index}>{recommendationText(item)}</p>
            ))}
          </section>
        </>
      ) : null}
    </aside>
  );
}

function AnalysisProgress({
  job,
  selectedPullRequests
}: {
  job: AnalysisJobStatusResponse;
  selectedPullRequests: PullRequestSummary[];
}) {
  const recentEvents = job.events.slice(-5).reverse();
  return (
    <section className="analysisProgress">
      <div className="progressHeader">
        <strong>분석 진행 중</strong>
        <span>{job.percent}%</span>
      </div>
      <div className="progressBar" aria-label="분석 진행률">
        <span style={{ width: `${Math.max(0, Math.min(100, job.percent))}%` }} />
      </div>
      <p className="muted">{job.current_step ?? "분석 단계를 준비하고 있습니다."}</p>
      <div className="jobPrSnapshot">
        {selectedPullRequests.map((pullRequest, index) => (
          <span
            className="legendChip"
            key={pullRequest.number}
            title={pullRequest.title}
          >
            <span className="legendSwatch" style={{ backgroundColor: colorForPrIndex(index) }} />
            #{pullRequest.number}
          </span>
        ))}
      </div>
      {recentEvents.length > 0 ? (
        <ol className="progressEvents">
          {recentEvents.map((event, index) => (
            <li key={`${event.timestamp}:${event.stage}:${index}`}>
              <span>{event.pr_number ? `PR #${event.pr_number} · ` : ""}{event.message}</span>
              <small>{progressStatusLabel(event.status)}</small>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

function SelectedPrPanel({
  pullRequests,
  onSelectFile
}: {
  pullRequests: PullRequestSummary[];
  onSelectFile: (fileId: number) => void;
}) {
  const [expandedPrNumber, setExpandedPrNumber] = useState<number | null>(null);
  const [collapsedPrNumbers, setCollapsedPrNumbers] = useState<number[]>([]);

  useEffect(() => {
    const currentNumbers = pullRequests.map((pullRequest) => pullRequest.number);
    setCollapsedPrNumbers((previous) => {
      const next = previous.filter((number) => currentNumbers.includes(number));
      return next.length === previous.length ? previous : next;
    });

    if (pullRequests.length === 0) {
      setExpandedPrNumber(null);
      return;
    }

    if (expandedPrNumber !== null && !currentNumbers.includes(expandedPrNumber)) {
      setExpandedPrNumber(null);
      return;
    }

    if (expandedPrNumber === null) {
      const nextPr = pullRequests.find((pullRequest) => !collapsedPrNumbers.includes(pullRequest.number));
      if (nextPr) {
        setExpandedPrNumber(nextPr.number);
      }
    }
  }, [collapsedPrNumbers, expandedPrNumber, pullRequests]);

  return (
    <section className="fileInspector prInspector">
      <h3>선택한 PR</h3>
      {pullRequests.length === 0 ? (
        <p className="muted">왼쪽 목록에서 PR을 선택하세요.</p>
      ) : null}
      {pullRequests.map((pullRequest, index) => {
        const expanded = expandedPrNumber === pullRequest.number;
        const color = colorForPrIndex(index);
        return (
          <article className={`selectedPrCard ${expanded ? "expanded" : ""}`} key={pullRequest.number}>
            <button
              className="selectedPrButton"
              type="button"
              onClick={() => {
                if (expanded) {
                  setCollapsedPrNumbers((previous) => (
                    previous.includes(pullRequest.number) ? previous : [...previous, pullRequest.number]
                  ));
                  setExpandedPrNumber(null);
                  return;
                }

                setCollapsedPrNumbers((previous) => previous.filter((number) => number !== pullRequest.number));
                setExpandedPrNumber(pullRequest.number);
              }}
              style={{ "--pr-color": color } as CSSProperties}
            >
              <span className="prColor" style={{ backgroundColor: color }} />
              <span>
                <strong>#{pullRequest.number} {pullRequest.title}</strong>
                <small>{pullRequest.file_count}개 파일 · +{pullRequest.additions} -{pullRequest.deletions}</small>
              </span>
            </button>
            {expanded ? (
              <div className="selectedPrDetails">
                <dl className="fileMetaGrid">
                  <div>
                    <dt>base</dt>
                    <dd>{pullRequest.base_ref}</dd>
                  </div>
                  <div>
                    <dt>head</dt>
                    <dd>{pullRequest.head_ref}</dd>
                  </div>
                </dl>
                <p className="prBodyText">{pullRequest.body_text || pullRequest.body_excerpt || "PR 설명이 없습니다."}</p>
                {pullRequest.labels.length > 0 ? (
                  <div className="labelRow">
                    {pullRequest.labels.map((label) => (
                      <span className="statusPill" key={label}>{label}</span>
                    ))}
                  </div>
                ) : null}
                <div className="changeSummary">
                  <h4>변경 파일</h4>
                  {pullRequest.changed_files.map((file) => (
                    <button
                      className="changeSummaryItem compact"
                      key={file.file_path_id}
                      type="button"
                      onClick={() => onSelectFile(file.file_path_id)}
                    >
                      <span className="prChangeColor" style={{ backgroundColor: color }} />
                      <span className="statusPill">{statusLabel(file.status)}</span>
                      <span className="changeSummaryText">
                        <strong>{file.path}</strong>
                        <small>{describeFileChange(file)}</small>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}

function SelectedFilePanel({
  currentUser,
  file,
  repository
}: {
  currentUser: AuthUser;
  file: SelectedFileInspector;
  repository: RepositorySummary;
}) {
  const [expandedChangeKey, setExpandedChangeKey] = useState<string | null>(null);

  useEffect(() => {
    setExpandedChangeKey(null);
  }, [file?.file_path_id]);

  const reasons = file.risk?.reasons ?? [];
  const detail = file.detail;
  return (
    <section className="fileInspector">
      <h3>선택한 파일</h3>
      <p className="selectedPath">{file.path}</p>
      <dl className="fileMetaGrid">
        <div>
          <dt>유형</dt>
          <dd>{nodeTypeLabel(file.node_type)}</dd>
        </div>
        <div>
          <dt>PRs</dt>
          <dd>{file.related_prs.length}개</dd>
        </div>
        {file.risk ? (
          <>
            <div>
              <dt>위험도</dt>
              <dd>{riskLevelLabel(file.risk.risk_level)}</dd>
            </div>
            <div>
              <dt>점수</dt>
              <dd>{file.risk.score}</dd>
            </div>
          </>
        ) : null}
      </dl>
      <div className="changeSummary">
        <h4>변경 내용</h4>
        {file.related_prs.length === 0 ? (
          <p className="muted">선택한 PR 중 이 파일을 바꾼 항목이 없습니다.</p>
        ) : null}
        {file.related_prs.map((item) => {
          const changeKey = `${item.number}:${item.file.path}`;
          const expanded = expandedChangeKey === changeKey;
          return (
            <div className={`changeCard ${expanded ? "expanded" : ""}`} key={changeKey}>
              <button
                className="changeSummaryItem"
                type="button"
                onClick={() => setExpandedChangeKey(expanded ? null : changeKey)}
              >
                <span className="prChangeColor" style={{ backgroundColor: item.color }} />
                <span className="statusPill">{statusLabel(item.file.status)}</span>
                <span className="changeSummaryText">
                  <strong>{describeFileChange(item.file)}</strong>
                  <small>
                    #{item.number} {item.title}
                    {item.file.hunk_count != null ? ` · hunk ${item.file.hunk_count}개` : ""}
                  </small>
                </span>
              </button>
              {expanded ? (
                <>
                  <PatchPreview patch={item.file.patch_excerpt} />
                  <CommentThread
                    currentUser={currentUser}
                    filePathId={item.file.file_path_id}
                    prNumber={item.number}
                    repository={repository}
                  />
                </>
              ) : null}
            </div>
          );
        })}
      </div>
      {reasons.length > 0 ? (
        <div className="reasonList">
          <h4>위험 근거</h4>
          {reasons.map((reason) => (
            <p key={reason}>{reason}</p>
          ))}
        </div>
      ) : null}
      {detail ? (
        <div className="evidenceBlock">
          <h4>근거</h4>
          <dl>
            <div>
              <dt>위험도</dt>
              <dd>{riskLevelLabel(String(detail.risk_level ?? ""))}</dd>
            </div>
            <div>
              <dt>점수</dt>
              <dd>{String(detail.score ?? "")}</dd>
            </div>
            <div>
              <dt>공개 표면</dt>
              <dd>{publicSurfaceLabel(String(detail.public_surface_level ?? ""))}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </section>
  );
}

function CommentThread({
  currentUser,
  filePathId,
  prNumber,
  repository
}: {
  currentUser: AuthUser;
  filePathId: number;
  prNumber: number;
  repository: RepositorySummary;
}) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchComments(repository.owner, repository.name, prNumber, filePathId)
      .then((response) => {
        if (!cancelled) {
          setComments(response.comments);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(errorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [filePathId, prNumber, repository.name, repository.owner]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const comment = await createComment(
        repository.owner,
        repository.name,
        prNumber,
        filePathId,
        trimmed
      );
      setComments((current) => [...current, comment]);
      setBody("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="commentThread">
      <div className="commentHeader">
        <h5>
          <MessageSquare size={14} />
          댓글
        </h5>
        <span>{comments.length}</span>
      </div>
      {loading ? <LoadingBlock label="댓글 불러오는 중" /> : null}
      {!loading && comments.length === 0 ? (
        <p className="muted">아직 댓글이 없습니다.</p>
      ) : null}
      <div className="commentList">
        {comments.map((comment) => (
          <article className="commentItem" key={comment.id}>
            <strong>{comment.author_login_id}</strong>
            <p>{comment.body}</p>
          </article>
        ))}
      </div>
      {error ? <InlineNotice text={error} tone="warning" /> : null}
      <form className="commentForm" onSubmit={submit}>
        <textarea
          placeholder={`${currentUser.user_id}로 댓글 작성`}
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        <button
          className="primaryButton"
          disabled={submitting || !body.trim()}
          type="submit"
        >
          {submitting ? <Loader2 className="spin" size={14} /> : null}
          댓글 등록
        </button>
      </form>
    </section>
  );
}

function PatchPreview({ patch }: { patch?: string | null }) {
  if (!patch) {
    return <p className="patchEmpty">표시할 patch 미리보기가 없습니다.</p>;
  }

  return (
    <pre className="patchPreview" aria-label="코드 변경 미리보기">
      {patch.split("\n").map((line, index) => (
        <span className={patchLineClass(line)} key={`${index}:${line}`}>
          {line || " "}
        </span>
      ))}
    </pre>
  );
}

function patchLineClass(line: string): string {
  if (line.startsWith("@@")) {
    return "patchLine patchLineMeta";
  }
  if (line.startsWith("+") && !line.startsWith("+++")) {
    return "patchLine patchLineAdd";
  }
  if (line.startsWith("-") && !line.startsWith("---")) {
    return "patchLine patchLineRemove";
  }
  return "patchLine";
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="loadingBlock">
      <Loader2 className="spin" size={16} />
      <span>{label}</span>
    </div>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="emptyState">
      <AlertTriangle size={18} />
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function InlineNotice({ text, tone = "info" }: { text: string; tone?: "info" | "warning" }) {
  return <p className={`inlineNotice ${tone}`}>{text}</p>;
}

function buildSelectedFileInspector({
  selectedFileId,
  canvas,
  overlay,
  riskFiles,
  detail
}: {
  selectedFileId: number | null;
  canvas: AtlasResponse["canvas_layout"] | null;
  overlay: AtlasResponse["pr_overlay"] | null;
  riskFiles: RiskFile[];
  detail: Record<string, unknown> | null;
}): SelectedFileInspector | null {
  if (selectedFileId == null) {
    return null;
  }

  const node = canvas?.nodes.find((item) => item.file_path_id === selectedFileId);
  const risk = riskFiles.find((item) => item.file_path_id === selectedFileId) ?? null;
  const relatedPrs = (overlay?.pull_requests ?? []).flatMap((pullRequest) =>
    pullRequest.files
      .filter((file) => file.file_path_id === selectedFileId)
      .map((file) => ({
        pull_request_id: pullRequest.pull_request_id,
        number: pullRequest.number,
        title: pullRequest.title,
        color: pullRequest.color,
        file
      }))
  );
  const detailPath = typeof detail?.path === "string" ? detail.path : null;
  const path = detailPath ?? risk?.path ?? relatedPrs[0]?.file.path ?? node?.path ?? node?.label;

  if (!path) {
    return null;
  }

  return {
    file_path_id: selectedFileId,
    path,
    label: basename(path),
    node_type: node?.node_type ?? "file",
    related_prs: relatedPrs,
    risk,
    detail
  };
}

function buildAnalysisRequest(
  repository: RepositorySummary,
  prNumbers: number[]
): AnalysisRunRequest {
  return {
    owner: repository.owner,
    repo: repository.name,
    pr_numbers: prNumbers,
    codeql_query_profile: "lite",
    skip_schema: false,
    use_llm: true
  };
}

function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  return new ApiError(500, errorMessage(error));
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "로그인이 필요합니다.";
    }
    if (error.status === 503 && error.detail.includes("OPENAI_API_KEY")) {
      return "OpenAI API 키가 필요합니다.";
    }
    if (error.status === 503) {
      return "Postgres 접속 또는 인증 정보를 확인해야 합니다.";
    }
    if (error.status === 404) {
      return "요청한 데이터를 찾을 수 없습니다.";
    }
    return translateKnownMessage(error.detail || error.message);
  }
  return error instanceof Error ? translateKnownMessage(error.message) : "요청에 실패했습니다.";
}

function translateKnownMessage(message: string): string {
  if (message.includes("Authentication required")) {
    return "로그인이 필요합니다.";
  }
  if (message.includes("Database is unavailable")) {
    return "Postgres 접속 또는 인증 정보를 확인해야 합니다.";
  }
  if (message.includes("OPENAI_API_KEY")) {
    return "OpenAI API 키가 필요합니다.";
  }
  if (message.includes("FastAPI")) {
    return "FastAPI 서버에 연결할 수 없습니다.";
  }
  if (message.includes("NetworkError") || message.includes("Failed to fetch")) {
    return "서버에 연결할 수 없습니다.";
  }
  return message || "요청에 실패했습니다.";
}

function overlayFileGroups(overlay: AtlasResponse["pr_overlay"] | null): Map<number, OverlayFileMarker[]> {
  const result = new Map<number, OverlayFileMarker[]>();
  for (const pr of overlay?.pull_requests ?? []) {
    for (const file of pr.files) {
      const markers = result.get(file.file_path_id) ?? [];
      markers.push({
        pull_request_id: pr.pull_request_id,
        number: pr.number,
        title: pr.title,
        color: pr.color
      });
      result.set(file.file_path_id, markers);
    }
  }
  return result;
}

function compactNodeLabel(node: AtlasNode): string {
  return basename(node.path ?? node.label);
}

function riskLevelLabel(level: string): string {
  return {
    low: "낮음",
    medium: "보통",
    high: "높음",
    critical: "치명적"
  }[level] ?? level;
}

function publicSurfaceLabel(level: string): string {
  return {
    public: "공개 API",
    core_internal: "핵심 내부",
    internal: "내부",
    low: "낮음",
    "": "-"
  }[level] ?? level;
}

function nodeTypeLabel(type: string): string {
  return {
    file: "파일",
    project_role: "프로젝트 역할"
  }[type] ?? type;
}

function statusLabel(status: string): string {
  return {
    added: "추가",
    modified: "수정",
    removed: "삭제",
    deleted: "삭제",
    renamed: "이름 변경",
    changed: "변경"
  }[status] ?? status;
}

function progressStatusLabel(status: string): string {
  return {
    queued: "대기",
    running: "진행",
    succeeded: "완료",
    ready: "완료",
    partial: "부분 완료",
    failed: "실패"
  }[status] ?? status;
}

function colorForPrNumber(number: number): string {
  return PR_COLORS[(Math.max(1, number) - 1) % PR_COLORS.length];
}

function colorForPrIndex(index: number): string {
  return PR_COLORS[Math.max(0, index) % PR_COLORS.length];
}

function actionLabel(action: string): string {
  return {
    manual_review: "수동 검토",
    rebase_before_merge: "병합 전 리베이스"
  }[action] ?? action;
}

function recommendationText(item: Record<string, unknown>): string {
  if (typeof item.reason === "string" && item.reason.trim()) {
    return item.reason;
  }
  if (typeof item.action === "string" && item.action.trim()) {
    return actionLabel(item.action);
  }
  return "검토 항목";
}

function basename(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

function describeFileChange(file: ChangedFileSummary): string {
  if (file.additions === 0 && file.deletions === 0) {
    return `${statusLabel(file.status)}됨, 라인 변화 없음`;
  }
  if (file.additions > 0 && file.deletions > 0) {
    return `${file.additions}줄 추가, ${file.deletions}줄 삭제`;
  }
  if (file.additions > 0) {
    return `${file.additions}줄 추가`;
  }
  return `${file.deletions}줄 삭제`;
}

function positionNodes(nodes: AtlasNode[]): AtlasNode[] {
  let fileFallbackIndex = 0;
  let roleFallbackIndex = 0;
  let otherFallbackIndex = 0;

  return nodes.map((node) => {
    if (node.x != null && node.y != null) {
      return {
        ...node,
        width: node.width ?? (node.node_type === "project_role" ? 180 : 150),
        height: node.height ?? 34
      };
    }

    if (node.node_type === "project_role") {
      const index = roleFallbackIndex;
      roleFallbackIndex += 1;
      return {
        ...node,
        x: 940,
        y: 120 + index * 78,
        width: node.width ?? 180,
        height: node.height ?? 38
      };
    }

    if (node.node_type === "file") {
      const index = fileFallbackIndex;
      fileFallbackIndex += 1;
      return {
        ...node,
        x: 120 + (index % 4) * 180,
        y: 120 + Math.floor(index / 4) * 90,
        width: node.width ?? 150,
        height: node.height ?? 34
      };
    }

    const index = otherFallbackIndex;
    otherFallbackIndex += 1;
    return {
      ...node,
      x: 120 + (index % 3) * 180,
      y: 420 + Math.floor(index / 3) * 90,
      width: node.width ?? 150,
      height: node.height ?? 34
    };
  });
}

function canvasBounds(nodes: AtlasNode[]): string {
  if (nodes.length === 0) {
    return "0 0 960 540";
  }
  const maxX = Math.max(...nodes.map((node) => (node.x ?? 0) + (node.width ?? 150)));
  const maxY = Math.max(...nodes.map((node) => (node.y ?? 0) + (node.height ?? 34)));
  return `0 0 ${Math.max(960, maxX + 120)} ${Math.max(540, maxY + 120)}`;
}
