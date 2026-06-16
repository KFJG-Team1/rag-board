import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const { MockApiError } = vi.hoisted(() => {
  class MockApiError extends Error {
    status: number;
    detail: string;

    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  }
  return { MockApiError };
});

vi.mock("./apiClient", () => ({
  ApiError: MockApiError,
  clearBasicAuthCredentials: vi.fn(),
  createComment: vi.fn(),
  createRepository: vi.fn(),
  deleteRepository: vi.fn(),
  fetchAnalysisJob: vi.fn(),
  fetchComments: vi.fn(),
  fetchMe: vi.fn(),
  fetchHealth: vi.fn(),
  fetchRepositories: vi.fn(),
  fetchPullRequests: vi.fn(),
  fetchAtlas: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshRepository: vi.fn(),
  runAnalysis: vi.fn(),
  setBasicAuthCredentials: vi.fn(),
  startAnalysisJob: vi.fn(),
  signup: vi.fn()
}));

import {
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
  startAnalysisJob,
  signup
} from "./apiClient";

const mockedHealth = vi.mocked(fetchHealth);
const mockedMe = vi.mocked(fetchMe);
const mockedRepositories = vi.mocked(fetchRepositories);
const mockedPullRequests = vi.mocked(fetchPullRequests);
const mockedAtlas = vi.mocked(fetchAtlas);
const mockedStartAnalysisJob = vi.mocked(startAnalysisJob);
const mockedFetchAnalysisJob = vi.mocked(fetchAnalysisJob);
const mockedCreateRepository = vi.mocked(createRepository);
const mockedRefreshRepository = vi.mocked(refreshRepository);
const mockedDeleteRepository = vi.mocked(deleteRepository);
const mockedLogin = vi.mocked(login);
const mockedSignup = vi.mocked(signup);
const mockedLogout = vi.mocked(logout);
const mockedFetchComments = vi.mocked(fetchComments);
const mockedCreateComment = vi.mocked(createComment);

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedHealth.mockResolvedValue({
      status: "ok",
      api_version: "v1",
      database_url_configured: true,
      codeql_available: true,
      codeql_path: "/opt/homebrew/bin/codeql",
      llm_configured: true,
      llm_model: "gpt-test"
    });
    mockedMe.mockResolvedValue({
      user: {
        id: 1,
        user_id: "tester"
      }
    });
    mockedLogin.mockResolvedValue({
      user: {
        id: 1,
        user_id: "tester"
      }
    });
    mockedSignup.mockResolvedValue({
      user: {
        id: 1,
        user_id: "tester"
      }
    });
    mockedLogout.mockResolvedValue({ message: "Logged out." });
    mockedRepositories.mockResolvedValue({
      repositories: [
        {
          id: 1,
          repo_key: "python/cpython",
          owner: "python",
          name: "cpython",
          pull_request_count: 1
        }
      ],
      limit: 12,
      offset: 0,
      total: 1
    });
    mockedCreateRepository.mockResolvedValue({
      repository: {
        id: 2,
        repo_key: "pallets/flask",
        owner: "pallets",
        name: "flask",
        pull_request_count: 1
      },
      imported_pr_count: 1,
      state: "open",
      page: 1,
      limit: 30,
      message: "Repository imported."
    });
    mockedRefreshRepository.mockResolvedValue({
      repository: {
        id: 1,
        repo_key: "python/cpython",
        owner: "python",
        name: "cpython",
        pull_request_count: 1
      },
      imported_pr_count: 1,
      state: "open",
      page: 1,
      limit: 30,
      message: "Repository refreshed."
    });
    mockedDeleteRepository.mockResolvedValue({
      repository: {
        repo_key: "python/cpython",
        owner: "python",
        name: "cpython"
      },
      removed_artifacts: [],
      message: "Repository deleted."
    });
    mockedPullRequests.mockResolvedValue({
      repository: {
        id: 1,
        repo_key: "python/cpython",
        owner: "python",
        name: "cpython",
        pull_request_count: 1
      },
      pull_requests: [
        {
          pull_request_id: 10,
          number: 123,
          title: "Change client request",
          body_text: "Full PR body with enough context for review.",
          body_excerpt: "Full PR body with enough context for review.",
          color: "#9333ea",
          url: "https://example.test/pr/123",
          state: "open",
          base_ref: "main",
          head_ref: "feature",
          base_sha: "base",
          head_sha: "head",
          labels: ["api"],
          updated_at: "2026-06-15T00:00:00Z",
          stored_at: "2026-06-15T00:00:00Z",
          file_count: 1,
          additions: 4,
          deletions: 1,
          changes: 5,
          changed_files: [
            {
              file_path_id: 20,
              path: "src/pkg/client.py",
              status: "modified",
              additions: 4,
              deletions: 1,
              changes: 5,
              hunk_count: 1,
              patch_excerpt: "@@ -1,2 +1,3 @@\n-old_request()\n+new_request()\n+validate_request()"
            }
          ]
        }
      ],
      state: "all",
      limit: 8,
      offset: 0,
      total: 1
    });
    mockedFetchComments.mockResolvedValue({
      comments: [
        {
          id: 1,
          pull_request_id: 10,
          file_path_id: 20,
          author_user_id: 1,
          author_login_id: "tester",
          body: "Looks good.",
          created_at: "2026-06-15T00:00:00Z",
          updated_at: "2026-06-15T00:00:00Z"
        }
      ]
    });
    mockedCreateComment.mockResolvedValue({
      id: 2,
      pull_request_id: 10,
      file_path_id: 20,
      author_user_id: 1,
      author_login_id: "tester",
      body: "Please check docs.",
      created_at: "2026-06-15T00:00:00Z",
      updated_at: "2026-06-15T00:00:00Z"
    });
    mockedAtlas.mockResolvedValue({
      canvas_layout: {
        repository_id: 1,
        nodes: [
          {
            id: "file:20",
            node_type: "file",
            file_path_id: 20,
            path: "src/pkg/client.py",
            label: "client.py",
            x: 120,
            y: 120,
            width: 140,
            height: 32
          },
          {
            id: "role:public_api",
            node_type: "project_role",
            label: "공개 API"
          }
        ],
        edges: [
          {
            id: "static:file:20-role:public_api",
            edge_type: "affects_project_role",
            source: "file:20",
            target: "role:public_api"
          }
        ]
      },
      pr_overlay: {
        repository_id: 1,
        selected_pr_ids: [10],
        pull_requests: [
          {
            pull_request_id: 10,
            number: 123,
            title: "Change client request",
            color: "#9333ea",
            files: [
              {
                file_path_id: 20,
                path: "src/pkg/client.py",
                status: "modified",
                additions: 4,
                deletions: 1,
                changes: 5,
                hunk_count: 1,
                patch_excerpt: "@@ -1,2 +1,3 @@\n-old_request()\n+new_request()\n+validate_request()"
              }
            ]
          }
        ]
      }
    });
    const analysisResult = {
      canvas_layout: {
        repository_id: 1,
        nodes: [
          {
            id: "file:20",
            node_type: "file",
            file_path_id: 20,
            path: "src/pkg/client.py",
            label: "client.py",
            x: 120,
            y: 120,
            width: 140,
            height: 32
          },
          {
            id: "role:public_api",
            node_type: "project_role",
            label: "공개 API"
          }
        ],
        edges: [
          {
            id: "static:file:20-role:public_api",
            edge_type: "affects_project_role",
            source: "file:20",
            target: "role:public_api"
          }
        ]
      },
      pr_overlay: {
        repository_id: 1,
        selected_pr_ids: [10],
        pull_requests: []
      },
      risk_analysis: {
        summary: "가장 위험한 파일은 src/pkg/client.py입니다.",
        files: [
          {
            file_path_id: 20,
            path: "src/pkg/client.py",
            node_id: "file:20",
            risk_level: "high",
            score: 68,
            reasons: ["CodeQL이 공개 표면 영향을 찾았습니다."]
          }
        ],
        errors: []
      },
      merge_recommendation: {
        recommended_actions: [
          {
            action: "manual_review",
            reason: "공개 API 동작을 검토하세요."
          }
        ]
      },
      file_details: {
        "20": {
          path: "src/pkg/client.py",
          risk_level: "high",
          score: 68,
          public_surface_level: "public"
        }
      },
      llm_analysis: {
        enabled: true,
        model: "gpt-test",
        summary: "LLM이 근거 기반 설명을 생성했습니다.",
        report: {
          review_focus: ["공개 API 동작 확인"],
          merge_notes: ["점수는 deterministic 근거를 따릅니다."]
        }
      }
    };
    mockedStartAnalysisJob.mockResolvedValue({
      job_id: "job-1",
      status: "queued",
      owner: "python",
      repo: "cpython",
      pr_numbers: [123]
    });
    mockedFetchAnalysisJob.mockResolvedValue({
      job_id: "job-1",
      status: "succeeded",
      owner: "python",
      repo: "cpython",
      pr_numbers: [123],
      current_step: "분석 완료",
      percent: 100,
      events: [
        {
          timestamp: "2026-06-15T00:00:00Z",
          stage: "complete",
          message: "분석이 완료되었습니다.",
          status: "succeeded",
          percent: 100
        }
      ],
      result: analysisResult,
      error: null,
      started_at: "2026-06-15T00:00:00Z",
      finished_at: "2026-06-15T00:00:01Z"
    });
  });

  it("shows auth screen before repository data when unauthenticated", async () => {
    mockedMe.mockRejectedValue(new MockApiError(401, "Authentication required."));

    render(<App />);

    expect(await screen.findByRole("button", { name: "로그인" })).toBeInTheDocument();
    expect(screen.getByText("회원가입")).toBeInTheDocument();
    expect(mockedRepositories).not.toHaveBeenCalled();
  });

  it("logs in and then loads repositories", async () => {
    const user = userEvent.setup();
    mockedMe.mockRejectedValue(new MockApiError(401, "Authentication required."));

    render(<App />);

    await user.type(await screen.findByLabelText("아이디"), "tester");
    await user.type(screen.getByLabelText("비밀번호"), "secret");
    await user.click(screen.getByRole("button", { name: "로그인하기" }));

    await waitFor(() => {
      expect(mockedLogin).toHaveBeenCalledWith("tester", "secret");
      expect(mockedRepositories).toHaveBeenCalledWith({ query: "", offset: 0, limit: 12 });
    });
  });

  it("shows database status when repository request returns 503", async () => {
    mockedRepositories.mockRejectedValue(new MockApiError(503, "Database is unavailable."));

    render(<App />);

    expect(await screen.findAllByText("Postgres 접속 또는 인증 정보를 확인해야 합니다.")).toHaveLength(2);
  });

  it("fetches atlas after PR selection", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));

    await waitFor(() => {
      expect(mockedAtlas).toHaveBeenCalledWith("python", "cpython", [123]);
    });
  });

  it("pins selected canvas file details in the right panel", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));
    await screen.findByText("client.py");

    const node = container.querySelector(".atlasNode");
    expect(node).not.toBeNull();
    await user.click(node as Element);

    expect(await screen.findByText("선택한 파일")).toBeInTheDocument();
    expect(screen.getAllByText("src/pkg/client.py").length).toBeGreaterThan(0);
    expect(screen.getByText("변경 내용")).toBeInTheDocument();
    expect(screen.getByText("4줄 추가, 1줄 삭제")).toBeInTheDocument();
    expect(screen.getAllByText(/#123 Change client request/).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /4줄 추가, 1줄 삭제/ }));

    expect(screen.getByText("+new_request()")).toBeInTheDocument();
    expect(await screen.findByText("Looks good.")).toBeInTheDocument();
  });

  it("creates a comment from an expanded change card", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));
    await screen.findByText("client.py");
    await user.click(container.querySelector(".atlasNode") as Element);
    await user.click(screen.getByRole("button", { name: /4줄 추가, 1줄 삭제/ }));
    await user.type(await screen.findByPlaceholderText("tester로 댓글 작성"), "Please check docs.");
    await user.click(screen.getByRole("button", { name: "댓글 등록" }));

    await waitFor(() => {
      expect(mockedCreateComment).toHaveBeenCalledWith(
        "python",
        "cpython",
        123,
        20,
        "Please check docs."
      );
    });
    expect(await screen.findByText("Please check docs.")).toBeInTheDocument();
  });

  it("searches repositories and PRs with server queries", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByPlaceholderText("레포지토리 검색"), "cpy");
    await user.click(screen.getByRole("button", { name: "검색" }));
    await waitFor(() => {
      expect(mockedRepositories).toHaveBeenLastCalledWith({ query: "cpy", offset: 0, limit: 12 });
    });

    await user.click(await screen.findByText("python/cpython"));
    await user.type(await screen.findByPlaceholderText("PR 검색"), "client");
    await user.click(screen.getAllByRole("button", { name: "검색" })[0]);

    await waitFor(() => {
      expect(mockedPullRequests).toHaveBeenLastCalledWith(
        "python",
        "cpython",
        { state: "all", query: "client", offset: 0, limit: 8 }
      );
    });
  });

  it("enables analysis after PR selection without manual paths", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));

    expect(await screen.findByRole("button", { name: /분석 실행/ })).toBeEnabled();
    expect(screen.queryByText("Advanced static analysis overrides")).not.toBeInTheDocument();
  });

  it("keeps the left PR list compact after selection", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));

    const prList = container.querySelector(".prList") as HTMLElement;
    expect(within(prList).queryByText("main ← feature")).not.toBeInTheDocument();
    expect(within(prList).queryByText("api")).not.toBeInTheDocument();
  });

  it("collapses an expanded PR description in the right panel when clicked again", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));
    const prButton = await screen.findByRole("button", { name: /#123 Change client request/ });

    expect(await screen.findByText("Full PR body with enough context for review.")).toBeInTheDocument();
    await user.click(prButton);

    expect(screen.queryByText("Full PR body with enough context for review.")).not.toBeInTheDocument();
  });

  it("disables analysis when OpenAI key is not configured", async () => {
    const user = userEvent.setup();
    mockedHealth.mockResolvedValue({
      status: "ok",
      api_version: "v1",
      database_url_configured: true,
      codeql_available: true,
      codeql_path: "/opt/homebrew/bin/codeql",
      llm_configured: false,
      llm_model: "gpt-test"
    });

    render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));

    expect(await screen.findByRole("button", { name: /분석 실행/ })).toBeDisabled();
    expect(screen.getByText(/OpenAI API 키가 필요합니다/)).toBeInTheDocument();
  });

  it("renders analysis risk files and selected file detail", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));
    await user.click(screen.getByRole("button", { name: /분석 실행/ }));

    expect(await screen.findByText("가장 위험한 파일은 src/pkg/client.py입니다.")).toBeInTheDocument();
    expect(screen.getAllByText("src/pkg/client.py").length).toBeGreaterThan(0);
    expect(screen.getAllByText("공개 API").length).toBeGreaterThan(0);
    expect(mockedStartAnalysisJob).toHaveBeenCalledWith({
      owner: "python",
      repo: "cpython",
      pr_numbers: [123],
      codeql_query_profile: "lite",
      skip_schema: false,
      use_llm: true
    });
    expect(mockedStartAnalysisJob.mock.calls[0][0]).not.toHaveProperty("repo_root");
    expect(mockedFetchAnalysisJob).toHaveBeenCalledWith("job-1");
  });

  it("keeps file and role atlas nodes from sharing coordinates after analysis", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.click(await screen.findByText("python/cpython"));
    await user.click(await screen.findByLabelText(/#123 Change client request/));
    await user.click(screen.getByRole("button", { name: /분석 실행/ }));
    await screen.findByText("가장 위험한 파일은 src/pkg/client.py입니다.");

    const fileNode = container.querySelector('[data-node-id="file:20"]');
    const roleNode = container.querySelector('[data-node-id="role:public_api"]');

    expect(fileNode).not.toBeNull();
    expect(roleNode).not.toBeNull();
    expect(`${fileNode?.getAttribute("data-x")}:${fileNode?.getAttribute("data-y")}`).not.toBe(
      `${roleNode?.getAttribute("data-x")}:${roleNode?.getAttribute("data-y")}`
    );
  });

  it("creates a repository from the board form", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /레포지토리 추가/ }));
    await user.type(screen.getByLabelText("소유자"), "pallets");
    await user.type(screen.getByLabelText("레포"), "flask");
    await user.click(screen.getByRole("button", { name: /가져오기/ }));

    await waitFor(() => {
      expect(mockedCreateRepository).toHaveBeenCalledWith({
        owner: "pallets",
        repo: "flask",
        state: "open",
        page: 1,
        limit: 30
      });
    });
  });
});
