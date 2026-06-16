from __future__ import annotations

import unittest
from base64 import b64encode
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from pr_atlas_mvp.api.app import create_app
from pr_atlas_mvp.ai_agent import AiAgentMessageResponse
from pr_atlas_mvp.api.dependencies import (
    get_ai_agent_service,
    get_api_service,
    get_auth_service,
    get_current_user,
)
from pr_atlas_mvp.api.services import (
    AuthError,
    DuplicateUserError,
    LLMConfigurationError,
    NotImportedError,
)


class ApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "user_id": "tester",
            "created_at": datetime(2026, 6, 15, tzinfo=UTC),
        }
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.client.close()

    def test_auth_routes_hide_password_without_cookie(self) -> None:
        service = FakeAuthService()
        self.app.dependency_overrides[get_auth_service] = lambda: service

        signup = self.client.post(
            "/api/v1/auth/signup",
            json={"user_id": "tester", "password": "secret"},
        )
        me = self.client.get("/api/v1/auth/me")
        logout = self.client.post("/api/v1/auth/logout")

        self.assertEqual(signup.status_code, 200)
        self.assertNotIn("password", signup.text)
        self.assertNotIn("set-cookie", signup.headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["user_id"], "tester")
        self.assertEqual(logout.status_code, 200)

    def test_auth_duplicate_and_login_failure(self) -> None:
        service = FakeAuthService()
        self.app.dependency_overrides[get_auth_service] = lambda: service

        duplicate = self.client.post(
            "/api/v1/auth/signup",
            json={"user_id": "dupe", "password": "secret"},
        )
        failed_login = self.client.post(
            "/api/v1/auth/login",
            json={"user_id": "tester", "password": "wrong"},
        )

        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(failed_login.status_code, 401)

    def test_protected_routes_require_login(self) -> None:
        self.app.dependency_overrides.pop(get_current_user, None)

        response = self.client.get("/api/v1/repositories")

        self.assertEqual(response.status_code, 401)

    def test_cookie_header_does_not_authenticate_protected_routes(self) -> None:
        self.app.dependency_overrides.pop(get_current_user, None)

        response = self.client.get(
            "/api/v1/repositories",
            headers={"Cookie": "session_id=fake-session-token"},
        )

        self.assertEqual(response.status_code, 401)

    def test_health_includes_llm_status_without_exposing_key(self) -> None:
        with (
            patch("pr_atlas_mvp.api.routes.is_openai_configured", return_value=True),
            patch("pr_atlas_mvp.api.routes.get_openai_model", return_value="gpt-test"),
        ):
            response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["llm_configured"])
        self.assertEqual(response.json()["llm_model"], "gpt-test")
        self.assertNotIn("OPENAI_API_KEY", response.text)

    def test_protected_routes_accept_basic_auth(self) -> None:
        self.app.dependency_overrides.pop(get_current_user, None)
        service = FakeService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        with (
            patch("pr_atlas_mvp.api.dependencies.get_database_url", return_value="postgresql://db"),
            patch("pr_atlas_mvp.api.dependencies.connect_database", return_value=nullcontext(object())),
            patch("pr_atlas_mvp.api.dependencies.AuthApiService", FakeCurrentUserService),
        ):
            response = self.client.get(
                "/api/v1/repositories",
                headers=_basic_auth_header("tester", "secret"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["repositories"][0]["repo_key"], "python/cpython")

    def test_analysis_rejects_empty_pr_numbers(self) -> None:
        response = self.client.post(
            "/api/v1/analysis",
            json={
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [],
                "codeql_results": "/tmp/results.sarif",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_analysis_rejects_negative_pr_numbers(self) -> None:
        response = self.client.post(
            "/api/v1/analysis",
            json={
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [-1],
                "codeql_results": "/tmp/results.sarif",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_analysis_accepts_automatic_static_analysis_input(self) -> None:
        service = FakeService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        response = self.client.post(
            "/api/v1/analysis",
            json={
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [123],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.analysis_pr_numbers, [123])
        self.assertEqual(service.analysis_codeql_query_profile, "lite")

    def test_analysis_requires_openai_key_when_llm_requested(self) -> None:
        service = LLMFailingService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        response = self.client.post(
            "/api/v1/analysis",
            json={
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [123],
                "use_llm": True,
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "OPENAI_API_KEY is required for LLM analysis.")

    def test_analysis_job_routes_return_progress_and_result(self) -> None:
        now = datetime(2026, 6, 15, tzinfo=UTC)
        with patch("pr_atlas_mvp.api.routes.analysis_job_manager") as manager:
            manager.start.return_value = {
                "job_id": "job-1",
                "status": "queued",
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [123],
            }
            manager.get.return_value = {
                "job_id": "job-1",
                "status": "succeeded",
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [123],
                "current_step": "분석 완료",
                "percent": 100,
                "events": [
                    {
                        "timestamp": now,
                        "stage": "complete",
                        "message": "분석이 완료되었습니다.",
                        "status": "succeeded",
                        "percent": 100,
                    }
                ],
                "result": _analysis_payload(),
                "error": None,
                "started_at": now,
                "finished_at": now,
            }

            started = self.client.post(
                "/api/v1/analysis/jobs",
                json={"owner": "python", "repo": "cpython", "pr_numbers": [123]},
            )
            status = self.client.get("/api/v1/analysis/jobs/job-1")

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["job_id"], "job-1")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["percent"], 100)
        self.assertEqual(status.json()["result"]["risk_analysis"]["files"], [])

    def test_analysis_returns_frontend_contract(self) -> None:
        service = FakeService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        response = self.client.post(
            "/api/v1/analysis",
            json={
                "owner": "python",
                "repo": "cpython",
                "pr_numbers": [123],
                "codeql_results": "/tmp/results.sarif",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            sorted(payload),
            [
                "canvas_layout",
                "file_details",
                "llm_analysis",
                "merge_recommendation",
                "pr_overlay",
                "risk_analysis",
            ],
        )
        self.assertEqual(service.analysis_pr_numbers, [123])

    def test_database_errors_are_sanitized_as_503(self) -> None:
        service = FailingService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        response = self.client.get("/api/v1/repositories")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Database is unavailable or credentials are invalid.",
        )

    def test_repository_and_pull_request_routes_return_expected_shape(self) -> None:
        service = FakeService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        repositories = self.client.get("/api/v1/repositories?query=cpy&limit=20&offset=20")
        pull_requests = self.client.get(
            "/api/v1/repositories/python/cpython/pull-requests?state=all&query=example&limit=20&offset=0"
        )

        self.assertEqual(repositories.status_code, 200)
        self.assertEqual(repositories.json()["repositories"][0]["repo_key"], "python/cpython")
        self.assertEqual(repositories.json()["total"], 1)
        self.assertEqual(service.repository_query, "cpy")
        self.assertEqual(pull_requests.status_code, 200)
        self.assertEqual(pull_requests.json()["pull_requests"][0]["number"], 123)
        self.assertEqual(pull_requests.json()["total"], 1)
        self.assertEqual(service.pr_query, "example")
        self.assertEqual(
            pull_requests.json()["pull_requests"][0]["changed_files"][0]["path"],
            "Lib/example.py",
        )

    def test_comment_routes_return_expected_shape(self) -> None:
        service = FakeService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        listed = self.client.get(
            "/api/v1/repositories/python/cpython/pull-requests/123/files/20/comments"
        )
        created = self.client.post(
            "/api/v1/repositories/python/cpython/pull-requests/123/files/20/comments",
            json={"body": "Please check docs."},
        )
        missing = self.client.get(
            "/api/v1/repositories/python/cpython/pull-requests/123/files/999/comments"
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["comments"][0]["body"], "Looks good.")
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["author_login_id"], "tester")
        self.assertEqual(missing.status_code, 404)

    def test_repository_crud_routes_return_expected_shape(self) -> None:
        service = FakeService()
        self.app.dependency_overrides[get_api_service] = lambda: service

        created = self.client.post(
            "/api/v1/repositories",
            json={"owner": "pallets", "repo": "flask", "state": "open", "limit": 30},
        )
        detail = self.client.get("/api/v1/repositories/python/cpython")
        refreshed = self.client.patch(
            "/api/v1/repositories/python/cpython",
            json={"owner": "ignored", "repo": "ignored", "state": "open", "limit": 30},
        )
        deleted = self.client.delete("/api/v1/repositories/python/cpython")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["repository"]["repo_key"], "pallets/flask")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["artifact_status"]["repo_checkout_exists"], False)
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json()["message"], "Repository refreshed.")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["message"], "Repository deleted.")

    def test_ai_agent_route_returns_expected_shape(self) -> None:
        service = FakeAgentService()
        self.app.dependency_overrides[get_ai_agent_service] = lambda: service

        response = self.client.post(
            "/api/v1/ai-agent/messages",
            json={"message": "https://github.com/pallets/flask 가져와줘"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "requires_input")
        self.assertEqual(response.json()["state"]["owner"], "pallets")
        self.assertEqual(service.last_message, "https://github.com/pallets/flask 가져와줘")

    def test_ai_agent_requires_openai_key_when_decision_loop_requested(self) -> None:
        self.app.dependency_overrides[get_ai_agent_service] = lambda: AgentLLMFailingService()

        response = self.client.post(
            "/api/v1/ai-agent/messages",
            json={"message": "pallets/flask 가져와줘"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "OPENAI_API_KEY is required for MCP agent runs.")


class FakeService:
    def __init__(self) -> None:
        self.analysis_pr_numbers: list[int] | None = None
        self.analysis_codeql_query_profile: str | None = None
        self.repository_query: str | None = None
        self.pr_query: str | None = None
        self.now = datetime(2026, 6, 15, tzinfo=UTC)

    def list_repositories(self, *, limit: int, offset: int, query: str = "") -> dict[str, Any]:
        self.repository_query = query
        return {
            "repositories": [
                {
                    "id": 1,
                    "repo_key": "python/cpython",
                    "owner": "python",
                    "name": "cpython",
                    "pull_request_count": 1,
                    "created_at": self.now,
                    "updated_at": self.now,
                }
            ],
            "limit": limit,
            "offset": offset,
            "total": 1,
        }

    def get_repository(self, *, owner: str, repo: str) -> dict[str, Any]:
        return {
            "repository": {
                "id": 1,
                "repo_key": f"{owner}/{repo}",
                "owner": owner,
                "name": repo,
                "pull_request_count": 1,
                "last_imported_at": self.now,
                "artifact_status": {
                    "repo_checkout_exists": False,
                    "worktrees_exist": False,
                    "codeql_dbs_exist": False,
                    "codeql_results_exist": False,
                },
                "created_at": self.now,
                "updated_at": self.now,
            },
            "artifact_status": {
                "repo_checkout_exists": False,
                "worktrees_exist": False,
                "codeql_dbs_exist": False,
                "codeql_results_exist": False,
            },
        }

    def create_repository(self, request: Any) -> dict[str, Any]:
        return {
            "repository": {
                "id": 2,
                "repo_key": f"{request.owner}/{request.repo}",
                "owner": request.owner,
                "name": request.repo,
                "pull_request_count": 1,
                "last_imported_at": self.now,
                "artifact_status": None,
                "created_at": self.now,
                "updated_at": self.now,
            },
            "imported_pr_count": 1,
            "state": request.state,
            "page": request.page,
            "limit": request.limit,
            "message": "Repository imported.",
        }

    def refresh_repository(self, *, owner: str, repo: str, request: Any) -> dict[str, Any]:
        return {
            "repository": {
                "id": 1,
                "repo_key": f"{owner}/{repo}",
                "owner": owner,
                "name": repo,
                "pull_request_count": 1,
                "last_imported_at": self.now,
                "artifact_status": None,
                "created_at": self.now,
                "updated_at": self.now,
            },
            "imported_pr_count": 1,
            "state": request.state,
            "page": request.page,
            "limit": request.limit,
            "message": "Repository refreshed.",
        }

    def delete_repository(self, *, owner: str, repo: str) -> dict[str, Any]:
        return {
            "repository": {
                "repo_key": f"{owner}/{repo}",
                "owner": owner,
                "name": repo,
            },
            "removed_artifacts": [],
            "message": "Repository deleted.",
        }

    def list_pull_requests(
        self,
        *,
        owner: str,
        repo: str,
        state: str,
        limit: int,
        offset: int,
        query: str = "",
    ) -> dict[str, Any]:
        self.pr_query = query
        return {
            "repository": {
                "id": 1,
                "repo_key": f"{owner}/{repo}",
                "owner": owner,
                "name": repo,
                "pull_request_count": 1,
                "created_at": self.now,
                "updated_at": self.now,
            },
            "pull_requests": [
                {
                    "pull_request_id": 10,
                    "number": 123,
                    "title": "Example PR",
                    "body_text": "Full PR body.",
                    "body_excerpt": "Full PR body.",
                    "color": "#9333ea",
                    "url": "https://example.test/pr/123",
                    "state": state if state != "all" else "open",
                    "base_ref": "main",
                    "head_ref": "feature",
                    "base_sha": "base",
                    "head_sha": "head",
                    "labels": ["test"],
                    "updated_at": self.now,
                    "stored_at": self.now,
                    "file_count": 1,
                    "additions": 3,
                    "deletions": 1,
                    "changes": 4,
                    "changed_files": [
                        {
                            "file_path_id": 20,
                            "path": "Lib/example.py",
                            "status": "modified",
                            "additions": 3,
                            "deletions": 1,
                            "changes": 4,
                        }
                    ],
                }
            ],
            "state": state,
            "limit": limit,
            "offset": offset,
            "total": 1,
        }

    def list_comments(
        self,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        file_path_id: int,
    ) -> dict[str, Any]:
        if file_path_id == 999:
            raise NotImportedError("Pull request does not change file.")
        return {
            "comments": [
                {
                    "id": 1,
                    "pull_request_id": 10,
                    "file_path_id": file_path_id,
                    "author_user_id": 1,
                    "author_login_id": "tester",
                    "body": "Looks good.",
                    "created_at": self.now,
                    "updated_at": self.now,
                }
            ]
        }

    def create_comment(
        self,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        file_path_id: int,
        author_user_id: int,
        body: str,
    ) -> dict[str, Any]:
        return {
            "id": 2,
            "pull_request_id": 10,
            "file_path_id": file_path_id,
            "author_user_id": author_user_id,
            "author_login_id": "tester",
            "body": body,
            "created_at": self.now,
            "updated_at": self.now,
        }

    def load_atlas(self, *, owner: str, repo: str, pr_numbers: tuple[int, ...]) -> dict[str, Any]:
        return {
            "canvas_layout": {"repository_id": 1, "nodes": [], "edges": []},
            "pr_overlay": {"selected_pr_ids": list(pr_numbers)},
        }

    def run_analysis(self, request: Any) -> dict[str, Any]:
        self.analysis_pr_numbers = list(request.pr_numbers)
        self.analysis_codeql_query_profile = request.codeql_query_profile
        return _analysis_payload()


class FailingService:
    def list_repositories(self, *, limit: int, offset: int, query: str = "") -> dict[str, Any]:
        raise SQLAlchemyError("postgresql://user:secret@localhost/db")


class LLMFailingService(FakeService):
    def run_analysis(self, request: Any) -> dict[str, Any]:
        raise LLMConfigurationError("OPENAI_API_KEY is required for LLM analysis.")


class FakeAgentService:
    def __init__(self) -> None:
        self.last_message: str | None = None

    def respond(self, request: Any) -> AiAgentMessageResponse:
        self.last_message = request.message
        return AiAgentMessageResponse(
            reply="pallets/flask에서 열린 PR 몇 개를 가져올까요?",
            status="requires_input",
            state={
                "owner": "pallets",
                "repo": "flask",
                "last_repository_key": "pallets/flask",
            },
            events=[],
        )


class AgentLLMFailingService:
    def respond(self, request: Any) -> dict[str, Any]:
        raise LLMConfigurationError("OPENAI_API_KEY is required for MCP agent runs.")


class FakeAuthService:
    def __init__(self) -> None:
        self.now = datetime(2026, 6, 15, tzinfo=UTC)

    def signup(self, *, user_id: str, password: str) -> dict[str, Any]:
        if user_id == "dupe":
            raise DuplicateUserError("User id already exists.")
        return self._payload(user_id)

    def login(self, *, user_id: str, password: str) -> dict[str, Any]:
        if password != "secret":
            raise AuthError("Invalid user id or password.")
        return self._payload(user_id)

    def logout(self) -> None:
        return None

    def _payload(self, user_id: str) -> dict[str, Any]:
        return {
            "user": {
                "id": 1,
                "user_id": user_id,
                "created_at": self.now,
            },
        }


class FakeCurrentUserService:
    def __init__(self, *, session: object) -> None:
        self.session = session

    def current_user(self, *, user_id: str, password: str) -> dict[str, Any]:
        if user_id != "tester" or password != "secret":
            raise AuthError("Invalid user id or password.")
        return {
            "id": 1,
            "user_id": user_id,
            "created_at": datetime(2026, 6, 15, tzinfo=UTC),
        }


def _basic_auth_header(user_id: str, password: str) -> dict[str, str]:
    encoded = b64encode(f"{user_id}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def _analysis_payload() -> dict[str, Any]:
    return {
        "canvas_layout": {"repository_id": 1, "nodes": [], "edges": []},
        "pr_overlay": {"selected_pr_ids": [10], "pull_requests": []},
        "risk_analysis": {"files": [], "errors": []},
        "merge_recommendation": {"recommended_order": []},
        "file_details": {},
        "llm_analysis": {"enabled": True, "summary": "LLM 요약"},
    }


if __name__ == "__main__":
    unittest.main()
