from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_VERSION = "v1"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 60.0
DEFAULT_AI_AGENT_PROMPT = PROJECT_ROOT / "pr_atlas_mvp" / "ai_agent" / "prompts" / "repository_import.md"
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def load_local_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def get_openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def is_openai_configured() -> bool:
    return bool(get_openai_api_key())


def get_openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def get_openai_timeout_seconds() -> float:
    value = os.environ.get("OPENAI_TIMEOUT_SECONDS", "").strip()
    if not value:
        return DEFAULT_OPENAI_TIMEOUT_SECONDS
    try:
        return max(1.0, float(value))
    except ValueError:
        return DEFAULT_OPENAI_TIMEOUT_SECONDS


def get_ai_agent_prompt_path() -> Path:
    value = os.environ.get("AI_AGENT_PROMPT_PATH", "").strip()
    if not value:
        return DEFAULT_AI_AGENT_PROMPT
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_ai_agent_mcp_command() -> str:
    value = os.environ.get("AI_AGENT_MCP_COMMAND", "").strip()
    if value:
        command = Path(value)
        return str(command if command.is_absolute() else PROJECT_ROOT / command)
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(venv_python if venv_python.exists() else Path(sys.executable))


def get_ai_agent_mcp_args() -> tuple[str, ...]:
    value = os.environ.get("AI_AGENT_MCP_ARGS", "").strip()
    return tuple(shlex.split(value)) if value else ("-m", "pr_atlas_mvp.mcp.server")


def get_ai_agent_mcp_cwd() -> Path:
    value = os.environ.get("AI_AGENT_MCP_CWD", "").strip()
    if not value:
        return PROJECT_ROOT
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
