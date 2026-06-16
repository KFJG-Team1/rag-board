from __future__ import annotations


MCP_SERVER_NAME = "pr_atlas"
MCP_TOOL_NAMES = (
    "import_repository",
    "refresh_repository",
    "list_repositories",
    "list_pull_requests",
    "run_analysis",
)


def is_import_tool(tool_name: str) -> bool:
    return tool_name in {"import_repository", f"{MCP_SERVER_NAME}__import_repository"}


def is_pull_request_tool(tool_name: str) -> bool:
    return tool_name in {"list_pull_requests", f"{MCP_SERVER_NAME}__list_pull_requests"}
