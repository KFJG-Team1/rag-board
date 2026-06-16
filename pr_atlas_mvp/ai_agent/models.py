from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


AgentStatus = Literal["running", "requires_input", "completed", "error"]


class AiAgentChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AiAgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str | None = None
    repo: str | None = None
    pr_limit: int | None = Field(default=None, ge=1, le=100)
    pr_state: Literal["open", "closed", "all"] = "open"
    page: int = Field(default=1, ge=1)
    imported: bool = False
    last_repository_key: str | None = None


class AiAgentMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    history: list[AiAgentChatMessage] = Field(default_factory=list, max_length=20)
    state: AiAgentState = Field(default_factory=AiAgentState)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank.")
        return value.strip()


class AiAgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    tool_name: str
    message: str
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)


class AiAgentMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    status: AgentStatus
    state: AiAgentState
    events: list[AiAgentEvent] = Field(default_factory=list)
    repository: dict[str, Any] | None = None
    pull_requests: list[dict[str, Any]] = Field(default_factory=list)
