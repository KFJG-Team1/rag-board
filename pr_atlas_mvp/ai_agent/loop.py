from __future__ import annotations

import json

from pr_atlas_mvp.ai_agent.models import AiAgentEvent, AiAgentMessageRequest, AiAgentState, AgentStatus
from pr_atlas_mvp.ai_agent.repo_parser import extract_pr_limit, parse_repository_ref
from pr_atlas_mvp.ai_agent.tools import is_import_tool, is_pull_request_tool


def build_agent_input(request: AiAgentMessageRequest) -> str:
    return json.dumps(
        {
            "latest_user_message": request.message,
            "conversation_history": [item.model_dump() for item in request.history[-12:]],
            "client_state": request.state.model_dump(),
        },
        ensure_ascii=False,
    )


def derive_state_from_run(
    request: AiAgentMessageRequest,
    *,
    events: list[AiAgentEvent],
) -> AiAgentState:
    state = request.state
    update: dict[str, object] = {}
    ref = parse_repository_ref(request.message)
    if ref is not None:
        update.update(
            {
                "owner": ref.owner,
                "repo": ref.repo,
                "last_repository_key": ref.repo_key,
            }
        )

    limit = extract_pr_limit(request.message)
    if limit is not None and 1 <= limit <= 100:
        update["pr_limit"] = limit

    if any(is_import_tool(event.tool_name) and event.ok for event in events):
        update["imported"] = True

    return state.model_copy(update=update) if update else state


def derive_status(reply: str, events: list[AiAgentEvent]) -> AgentStatus:
    if any(is_import_tool(event.tool_name) and event.ok for event in events):
        return "completed"
    if any(is_pull_request_tool(event.tool_name) and event.ok for event in events):
        return "completed"
    if any(not event.ok for event in events):
        return "error"
    if _looks_like_question(reply):
        return "requires_input"
    return "completed"


def extract_repository(events: list[AiAgentEvent]) -> dict | None:
    for event in reversed(events):
        repository = event.data.get("repository")
        if isinstance(repository, dict):
            return repository
    return None


def extract_pull_requests(events: list[AiAgentEvent]) -> list[dict]:
    for event in reversed(events):
        pull_requests = event.data.get("pull_requests")
        if isinstance(pull_requests, list):
            return [item for item in pull_requests if isinstance(item, dict)]
    return []


def _looks_like_question(reply: str) -> bool:
    lowered = reply.lower()
    return "?" in reply or "까요" in reply or "몇 개" in reply or "how many" in lowered
