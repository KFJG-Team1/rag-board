from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar

from fastapi.encoders import jsonable_encoder
from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from pr_atlas_mvp.analysis.models import DEFAULT_CODEQL_QUERY_PROFILE
from pr_atlas_mvp.analysis.pipeline import run_analysis as run_analysis_pipeline
from pr_atlas_mvp.api.config import get_database_url, load_local_env
from pr_atlas_mvp.api.schemas import AnalysisRunRequest, RepositoryImportRequest
from pr_atlas_mvp.api.services import AtlasApiService, DuplicateRepositoryError
from pr_atlas_mvp.postgres.connection import connect_database


T = TypeVar("T")
RepositoryState = Literal["open", "closed", "all"]


def create_mcp_server() -> FastMCP:
    server = FastMCP(
        "pr-atlas",
        instructions=(
            "Tools for importing public GitHub repositories, listing imported repositories, "
            "listing imported pull requests, and running PR Collision Atlas analysis."
        ),
    )

    @server.tool()
    def import_repository(
        owner: str,
        repo: str,
        limit: int,
        state: RepositoryState = "open",
        page: int = 1,
    ) -> dict[str, Any]:
        """Import a public GitHub repository's pull requests. Refreshes if it already exists."""
        return _with_service(
            lambda service: import_repository_with_service(
                service,
                owner=owner,
                repo=repo,
                limit=limit,
                state=state,
                page=page,
            )
        )

    @server.tool()
    def refresh_repository(
        owner: str,
        repo: str,
        limit: int,
        state: RepositoryState = "open",
        page: int = 1,
    ) -> dict[str, Any]:
        """Refresh an already imported public GitHub repository's pull requests."""
        return _with_service(
            lambda service: refresh_repository_with_service(
                service,
                owner=owner,
                repo=repo,
                limit=limit,
                state=state,
                page=page,
            )
        )

    @server.tool()
    def list_repositories(
        query: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List repositories currently imported into PR Collision Atlas."""
        _validate_page(limit=limit, offset=offset)
        return _with_service(
            lambda service: service.list_repositories(
                query=query,
                limit=limit,
                offset=offset,
            )
        )

    @server.tool()
    def list_pull_requests(
        owner: str,
        repo: str,
        state: RepositoryState = "all",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List imported pull requests for a repository."""
        _validate_owner_repo(owner, repo)
        _validate_page(limit=limit, offset=offset)
        return _with_service(
            lambda service: service.list_pull_requests(
                owner=owner,
                repo=repo,
                state=state,
                limit=limit,
                offset=offset,
                query="",
            )
        )

    @server.tool()
    def run_analysis(
        owner: str,
        repo: str,
        pr_numbers: list[int],
        use_llm: bool = True,
    ) -> dict[str, Any]:
        """Run existing PR Collision Atlas analysis for imported PR numbers."""
        _validate_owner_repo(owner, repo)
        if not pr_numbers:
            raise ValueError("pr_numbers must contain at least one PR number.")
        request = AnalysisRunRequest(
            owner=owner,
            repo=repo,
            pr_numbers=pr_numbers,
            codeql_query_profile=DEFAULT_CODEQL_QUERY_PROFILE,
            use_llm=use_llm,
        )
        return _with_service(lambda service: service.run_analysis(request))

    return server


def import_repository_with_service(
    service: AtlasApiService,
    *,
    owner: str,
    repo: str,
    limit: int,
    state: RepositoryState = "open",
    page: int = 1,
) -> dict[str, Any]:
    _validate_owner_repo(owner, repo)
    _validate_import_window(limit=limit, page=page)
    request = RepositoryImportRequest(
        owner=owner,
        repo=repo,
        state=state,
        page=page,
        limit=limit,
    )
    operation = "created"
    try:
        payload = service.create_repository(request)
    except DuplicateRepositoryError:
        operation = "refreshed"
        payload = service.refresh_repository(owner=owner, repo=repo, request=request)
    return _tool_payload(payload, operation=operation)


def refresh_repository_with_service(
    service: AtlasApiService,
    *,
    owner: str,
    repo: str,
    limit: int,
    state: RepositoryState = "open",
    page: int = 1,
) -> dict[str, Any]:
    _validate_owner_repo(owner, repo)
    _validate_import_window(limit=limit, page=page)
    request = RepositoryImportRequest(
        owner=owner,
        repo=repo,
        state=state,
        page=page,
        limit=limit,
    )
    return _tool_payload(
        service.refresh_repository(owner=owner, repo=repo, request=request),
        operation="refreshed",
    )


def _with_service(action: Callable[[AtlasApiService], T]) -> T:
    session = _new_session()
    try:
        return jsonable_encoder(action(_service_for_session(session)))
    finally:
        session.close()


def _service_for_session(session: Session) -> AtlasApiService:
    return AtlasApiService(session=session, runner=run_analysis_pipeline)


def _new_session() -> Session:
    load_local_env()
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return connect_database(database_url)


def _tool_payload(payload: dict[str, Any], *, operation: str) -> dict[str, Any]:
    encoded = jsonable_encoder(payload)
    encoded["operation"] = operation
    return encoded


def _validate_owner_repo(owner: str, repo: str) -> None:
    RepositoryImportRequest(owner=owner, repo=repo)


def _validate_import_window(*, limit: int, page: int) -> None:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")
    if page < 1:
        raise ValueError("page must be greater than or equal to 1.")


def _validate_page(*, limit: int, offset: int) -> None:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0.")


def main() -> None:
    load_local_env()
    create_mcp_server().run("stdio")


if __name__ == "__main__":
    main()
