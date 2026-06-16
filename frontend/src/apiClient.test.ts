import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  clearBasicAuthCredentials,
  createComment,
  createRepository,
  deleteRepository,
  fetchAtlas,
  fetchAnalysisJob,
  fetchComments,
  fetchPullRequests,
  fetchRepositories,
  login,
  refreshRepository,
  runAnalysis,
  sendAiAgentMessage,
  setBasicAuthCredentials,
  startAnalysisJob,
  signup
} from "./apiClient";

const AUTH_HEADER = "Basic dGVzdGVyOnNlY3JldA==";

describe("apiClient", () => {
  beforeEach(() => {
    setBasicAuthCredentials({ userId: "tester", password: "secret" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({
          canvas_layout: { nodes: [], edges: [] },
          pr_overlay: { pull_requests: [] },
          risk_analysis: { files: [] },
          merge_recommendation: {},
          file_details: {}
        })
      )
    );
  });

  afterEach(() => {
    clearBasicAuthCredentials();
    vi.unstubAllGlobals();
  });

  it("calls pull request endpoint with encoded owner and repo", async () => {
    await fetchPullRequests("python", "cpython", { query: "client", limit: 20, offset: 40 });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories/python/cpython/pull-requests?state=all&query=client&limit=20&offset=40",
      { headers: { authorization: AUTH_HEADER } }
    );
  });

  it("calls repository endpoint with search pagination", async () => {
    await fetchRepositories({ query: "cpy", limit: 20, offset: 20 });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories?query=cpy&limit=20&offset=20",
      { headers: { authorization: AUTH_HEADER } }
    );
  });

  it("calls atlas endpoint with selected PR numbers", async () => {
    await fetchAtlas("python", "cpython", [10, 12]);

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories/python/cpython/atlas?prs=10%2C12",
      { headers: { authorization: AUTH_HEADER } }
    );
  });

  it("posts analysis request body", async () => {
    await runAnalysis({
      owner: "python",
      repo: "cpython",
      pr_numbers: [10]
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analysis",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: AUTH_HEADER,
          "content-type": "application/json"
        }),
        body: JSON.stringify({
          owner: "python",
          repo: "cpython",
          pr_numbers: [10]
        })
      })
    );
  });

  it("starts and polls analysis jobs", async () => {
    await startAnalysisJob({
      owner: "python",
      repo: "cpython",
      pr_numbers: [10],
      codeql_query_profile: "lite",
      skip_schema: false,
      use_llm: true
    });
    await fetchAnalysisJob("job-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analysis/jobs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: AUTH_HEADER,
          "content-type": "application/json"
        }),
        body: JSON.stringify({
          owner: "python",
          repo: "cpython",
          pr_numbers: [10],
          codeql_query_profile: "lite",
          skip_schema: false,
          use_llm: true
        })
      })
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analysis/jobs/job-1",
      { headers: { authorization: AUTH_HEADER } }
    );
  });

  it("posts repository create request body", async () => {
    await createRepository({ owner: "pallets", repo: "flask", state: "open", limit: 30 });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: AUTH_HEADER,
          "content-type": "application/json"
        }),
        body: JSON.stringify({ owner: "pallets", repo: "flask", state: "open", limit: 30 })
      })
    );
  });

  it("posts AI agent messages", async () => {
    await sendAiAgentMessage({
      message: "https://github.com/pallets/flask 가져와줘",
      state: { owner: null, repo: null }
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/ai-agent/messages",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: AUTH_HEADER,
          "content-type": "application/json"
        }),
        body: JSON.stringify({
          message: "https://github.com/pallets/flask 가져와줘",
          state: { owner: null, repo: null }
        })
      })
    );
  });

  it("calls repository refresh and delete endpoints", async () => {
    await refreshRepository("pallets", "flask", { owner: "pallets", repo: "flask", state: "open" });
    await deleteRepository("pallets", "flask");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories/pallets/flask",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({ authorization: AUTH_HEADER })
      })
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories/pallets/flask",
      { method: "DELETE", headers: { authorization: AUTH_HEADER } }
    );
  });

  it("calls auth endpoints", async () => {
    await login("tester", "secret");
    await signup("new-user", "secret");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ user_id: "tester", password: "secret" })
      })
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/auth/signup",
      expect.objectContaining({
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ user_id: "new-user", password: "secret" })
      })
    );
  });

  it("calls comment endpoints", async () => {
    await fetchComments("python", "cpython", 123, 20);
    await createComment("python", "cpython", 123, 20, "Looks good.");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories/python/cpython/pull-requests/123/files/20/comments",
      { headers: { authorization: AUTH_HEADER } }
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/repositories/python/cpython/pull-requests/123/files/20/comments",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: AUTH_HEADER,
          "content-type": "application/json"
        }),
        body: JSON.stringify({ body: "Looks good." })
      })
    );
  });
});
