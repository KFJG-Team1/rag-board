from __future__ import annotations

import asyncio
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pr_atlas_mvp.ai_agent.loop import (
    build_agent_input,
    derive_state_from_run,
    derive_status,
    extract_pull_requests,
    extract_repository,
)
from pr_atlas_mvp.ai_agent.models import AiAgentEvent, AiAgentMessageRequest, AiAgentMessageResponse
from pr_atlas_mvp.ai_agent.tools import MCP_SERVER_NAME, MCP_TOOL_NAMES


class AiAgentLLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpAgentConfig:
    model: str
    timeout_seconds: float
    prompt_path: Path
    mcp_command: str
    mcp_args: tuple[str, ...]
    mcp_cwd: Path


class AgentsSdkMcpRunner:
    def __init__(self, config: McpAgentConfig) -> None:
        self.config = config

    def run(self, request: AiAgentMessageRequest) -> AiAgentMessageResponse:
        return asyncio.run(self._run_async(request))

    async def _run_async(self, request: AiAgentMessageRequest) -> AiAgentMessageResponse:
        _require_openai_key()
        try:
            from agents import Agent, Runner
            from agents.mcp import MCPServerStdio, create_static_tool_filter
        except ImportError as exc:
            raise AiAgentLLMError("openai-agents package is required for MCP agent runs.") from exc

        events = [
            AiAgentEvent(
                type="mcp:list_tools",
                tool_name="list_tools",
                message="MCP tools will be listed by the OpenAI Agents SDK.",
            )
        ]
        async with MCPServerStdio(
            name=MCP_SERVER_NAME,
            params={
                "command": self.config.mcp_command,
                "args": list(self.config.mcp_args),
                "cwd": self.config.mcp_cwd,
                "env": {
                    **os.environ,
                    "PYTHONPATH": _pythonpath_with_project_root(self.config.mcp_cwd),
                },
            },
            cache_tools_list=False,
            client_session_timeout_seconds=self.config.timeout_seconds,
            tool_filter=create_static_tool_filter(allowed_tool_names=list(MCP_TOOL_NAMES)),
        ) as server:
            agent = Agent(
                name="PR Collision Atlas MCP Agent",
                instructions=_read_prompt(self.config.prompt_path),
                model=self.config.model,
                mcp_servers=[server],
                mcp_config={
                    "convert_schemas_to_strict": True,
                    "include_server_in_tool_names": False,
                },
            )
            result = await Runner.run(agent, build_agent_input(request))

        reply = _final_output(result)
        events.extend(_events_from_result(result))
        state = derive_state_from_run(request, events=events)
        return AiAgentMessageResponse(
            reply=reply,
            status=derive_status(reply, events),
            state=state,
            events=events,
            repository=extract_repository(events),
            pull_requests=extract_pull_requests(events),
        )


def split_mcp_args(value: str) -> tuple[str, ...]:
    return tuple(shlex.split(value)) if value.strip() else ()


def _pythonpath_with_project_root(project_root: Path) -> str:
    current = os.environ.get("PYTHONPATH", "").strip()
    root = str(project_root)
    if not current:
        return root
    parts = current.split(os.pathsep)
    return current if root in parts else os.pathsep.join([root, current])


def _require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise AiAgentLLMError("OPENAI_API_KEY is required for MCP agent runs.")


def _read_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise AiAgentLLMError(f"AI agent prompt file is unavailable: {path}") from exc


def _final_output(result: Any) -> str:
    value = getattr(result, "final_output", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is not None:
        return str(value).strip()
    return "요청을 처리했습니다."


def _events_from_result(result: Any) -> list[AiAgentEvent]:
    events: list[AiAgentEvent] = []
    for item in getattr(result, "new_items", []) or []:
        tool_name = _tool_name_from_item(item)
        if tool_name is None:
            continue
        events.append(
            AiAgentEvent(
                type="mcp:tool_call",
                tool_name=tool_name,
                message=f"MCP tool called: {tool_name}",
                data=_data_from_item(item),
            )
        )
    return events


def _tool_name_from_item(item: Any) -> str | None:
    for candidate in (
        getattr(item, "tool_name", None),
        getattr(item, "name", None),
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    raw_item = getattr(item, "raw_item", None)
    for candidate in (
        getattr(raw_item, "name", None),
        getattr(raw_item, "tool_name", None),
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    data = getattr(item, "data", None)
    if isinstance(data, dict):
        for key in ("name", "tool_name"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _data_from_item(item: Any) -> dict[str, Any]:
    for attr in ("output", "content", "data"):
        value = getattr(item, attr, None)
        if isinstance(value, dict):
            return value
    raw_item = getattr(item, "raw_item", None)
    if isinstance(raw_item, dict):
        return raw_item
    return {}
