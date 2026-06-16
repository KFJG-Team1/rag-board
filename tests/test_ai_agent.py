from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pr_atlas_mvp.ai_agent import AiAgentMessageResponse
from pr_atlas_mvp.ai_agent.models import AiAgentMessageRequest, AiAgentState
from pr_atlas_mvp.ai_agent.repo_parser import extract_pr_limit, parse_repository_ref
from pr_atlas_mvp.ai_agent.service import AiAgentService
from pr_atlas_mvp.api.services import DuplicateRepositoryError
from pr_atlas_mvp.mcp.server import import_repository_with_service, refresh_repository_with_service


class AiAgentParserTests(unittest.TestCase):
    def test_parse_repository_ref_accepts_github_url_and_owner_repo(self) -> None:
        url_ref = parse_repository_ref("https://github.com/pallets/flask/pulls")
        short_ref = parse_repository_ref("pallets/flask")

        self.assertIsNotNone(url_ref)
        self.assertEqual(url_ref.owner, "pallets")
        self.assertEqual(url_ref.repo, "flask")
        self.assertIsNotNone(short_ref)
        self.assertEqual(short_ref.repo_key, "pallets/flask")

    def test_parse_repository_ref_rejects_invalid_input(self) -> None:
        self.assertIsNone(parse_repository_ref("just some text"))

    def test_extract_pr_limit_from_korean_followup(self) -> None:
        self.assertEqual(extract_pr_limit("열린 PR 5개"), 5)
        self.assertEqual(extract_pr_limit("20"), 20)


class McpToolTests(unittest.TestCase):
    def test_import_repository_uses_existing_import_foundation(self) -> None:
        service = FakeAtlasService()

        payload = import_repository_with_service(
            service,
            owner="pallets",
            repo="flask",
            limit=10,
        )

        self.assertEqual(service.created_limit, 10)
        self.assertEqual(payload["operation"], "created")
        self.assertEqual(payload["repository"]["repo_key"], "pallets/flask")

    def test_duplicate_repository_refreshes_instead_of_failing(self) -> None:
        service = FakeAtlasService(duplicate=True)

        payload = import_repository_with_service(
            service,
            owner="pallets",
            repo="flask",
            limit=5,
        )

        self.assertTrue(service.refreshed)
        self.assertEqual(payload["operation"], "refreshed")

    def test_import_limit_rejects_over_100(self) -> None:
        with self.assertRaises(ValueError):
            import_repository_with_service(
                FakeAtlasService(),
                owner="pallets",
                repo="flask",
                limit=101,
            )

    def test_refresh_repository_tool_calls_refresh(self) -> None:
        service = FakeAtlasService()

        payload = refresh_repository_with_service(
            service,
            owner="pallets",
            repo="flask",
            limit=3,
        )

        self.assertTrue(service.refreshed)
        self.assertEqual(payload["operation"], "refreshed")


class AiAgentServiceTests(unittest.TestCase):
    def test_service_uses_injected_runner(self) -> None:
        runner = FakeRunner(
            AiAgentMessageResponse(
                reply="몇 개의 열린 PR을 가져올까요?",
                status="requires_input",
                state=AiAgentState(owner="pallets", repo="flask", last_repository_key="pallets/flask"),
                events=[],
            )
        )

        response = AiAgentService(runner=runner).respond(
            AiAgentMessageRequest(message="https://github.com/pallets/flask 가져와줘")
        )

        self.assertEqual(response.status, "requires_input")
        self.assertEqual(response.state.owner, "pallets")
        self.assertEqual(runner.last_request.message, "https://github.com/pallets/flask 가져와줘")

    def test_service_builds_agents_sdk_config_from_env_helpers(self) -> None:
        runner_holder: dict[str, Any] = {}

        class RecordingRunner(FakeRunner):
            def __init__(self, config: Any) -> None:
                runner_holder["config"] = config
                super().__init__(
                    AiAgentMessageResponse(
                        reply="가져왔습니다.",
                        status="completed",
                        state=AiAgentState(imported=True),
                        events=[],
                    )
                )

        with (
            patch("pr_atlas_mvp.ai_agent.service.is_openai_configured", return_value=True),
            patch("pr_atlas_mvp.ai_agent.service.AgentsSdkMcpRunner", RecordingRunner),
            patch("pr_atlas_mvp.ai_agent.service.get_openai_model", return_value="gpt-test"),
            patch("pr_atlas_mvp.ai_agent.service.get_openai_timeout_seconds", return_value=3.0),
            patch(
                "pr_atlas_mvp.ai_agent.service.get_ai_agent_prompt_path",
                return_value=Path("/tmp/repository_import.md"),
            ),
            patch("pr_atlas_mvp.ai_agent.service.get_ai_agent_mcp_command", return_value=".venv/bin/python"),
            patch(
                "pr_atlas_mvp.ai_agent.service.get_ai_agent_mcp_args",
                return_value=("-m", "pr_atlas_mvp.mcp.server"),
            ),
            patch("pr_atlas_mvp.ai_agent.service.get_ai_agent_mcp_cwd", return_value=Path("/repo")),
        ):
            response = AiAgentService().respond(AiAgentMessageRequest(message="10개"))

        self.assertEqual(response.status, "completed")
        config = runner_holder["config"]
        self.assertEqual(config.model, "gpt-test")
        self.assertEqual(config.mcp_command, ".venv/bin/python")
        self.assertEqual(config.mcp_args, ("-m", "pr_atlas_mvp.mcp.server"))
        self.assertEqual(config.mcp_cwd, Path("/repo"))


class FakeRunner:
    def __init__(self, response: AiAgentMessageResponse) -> None:
        self.response = response
        self.last_request: AiAgentMessageRequest | None = None

    def run(self, request: AiAgentMessageRequest) -> AiAgentMessageResponse:
        self.last_request = request
        return self.response


class FakeAtlasService:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.refreshed = False
        self.created_limit: int | None = None
        self.now = datetime(2026, 6, 15, tzinfo=UTC)

    def create_repository(self, request: Any) -> dict[str, Any]:
        if self.duplicate:
            raise DuplicateRepositoryError("Repository already exists.")
        self.created_limit = request.limit
        return self._import_payload(request, "Repository imported.")

    def refresh_repository(self, *, owner: str, repo: str, request: Any) -> dict[str, Any]:
        self.refreshed = True
        return self._import_payload(request, "Repository refreshed.")

    def _import_payload(self, request: Any, message: str) -> dict[str, Any]:
        return {
            "repository": {
                "id": 1,
                "repo_key": f"{request.owner}/{request.repo}",
                "owner": request.owner,
                "name": request.repo,
                "pull_request_count": request.limit,
                "created_at": self.now,
                "updated_at": self.now,
            },
            "imported_pr_count": request.limit,
            "state": request.state,
            "page": request.page,
            "limit": request.limit,
            "message": message,
        }


if __name__ == "__main__":
    unittest.main()
