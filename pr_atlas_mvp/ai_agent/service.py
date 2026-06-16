from __future__ import annotations

from typing import Protocol

from pr_atlas_mvp.ai_agent.llm import AgentsSdkMcpRunner, AiAgentLLMError, McpAgentConfig
from pr_atlas_mvp.ai_agent.models import AiAgentMessageRequest, AiAgentMessageResponse
from pr_atlas_mvp.api.config import (
    get_ai_agent_mcp_args,
    get_ai_agent_mcp_command,
    get_ai_agent_mcp_cwd,
    get_ai_agent_prompt_path,
    get_openai_model,
    get_openai_timeout_seconds,
    is_openai_configured,
)
from pr_atlas_mvp.api.services import LLMConfigurationError


class AiAgentRunner(Protocol):
    def run(self, request: AiAgentMessageRequest) -> AiAgentMessageResponse:
        ...


class AiAgentService:
    def __init__(
        self,
        *,
        runner: AiAgentRunner | None = None,
    ) -> None:
        self.runner = runner

    def respond(self, request: AiAgentMessageRequest) -> AiAgentMessageResponse:
        if self.runner is None and not is_openai_configured():
            raise LLMConfigurationError("OPENAI_API_KEY is required for MCP agent runs.")
        runner = self.runner or AgentsSdkMcpRunner(
            McpAgentConfig(
                model=get_openai_model(),
                timeout_seconds=get_openai_timeout_seconds(),
                prompt_path=get_ai_agent_prompt_path(),
                mcp_command=get_ai_agent_mcp_command(),
                mcp_args=get_ai_agent_mcp_args(),
                mcp_cwd=get_ai_agent_mcp_cwd(),
            )
        )
        try:
            return runner.run(request)
        except AiAgentLLMError as exc:
            raise LLMConfigurationError(str(exc)) from exc
