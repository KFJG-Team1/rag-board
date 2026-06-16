from __future__ import annotations

import shutil
from typing import Any, Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from pr_atlas_mvp.api.analysis_jobs import (
    AnalysisJobNotFoundError,
    analysis_job_manager,
)
from pr_atlas_mvp.api.config import (
    API_VERSION,
    get_database_url,
    get_openai_model,
    is_openai_configured,
)
from pr_atlas_mvp.api.dependencies import (
    get_ai_agent_service,
    get_api_service,
    get_auth_service,
    get_current_user,
)
from pr_atlas_mvp.ai_agent import (
    AiAgentMessageRequest,
    AiAgentMessageResponse,
    AiAgentService,
)
from pr_atlas_mvp.api.schemas import (
    AnalysisOutputResponse,
    AnalysisJobStartResponse,
    AnalysisJobStatusResponse,
    AnalysisRunRequest,
    AtlasResponse,
    AuthRequest,
    AuthResponse,
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    HealthResponse,
    LogoutResponse,
    PullRequestListResponse,
    RepositoryDetailResponse,
    RepositoryImportRequest,
    RepositoryImportResponse,
    RepositoryListResponse,
)
from pr_atlas_mvp.api.services import (
    AuthApiService,
    AuthError,
    AtlasApiService,
    DuplicateRepositoryError,
    DuplicateUserError,
    GitHubImportError,
    LLMConfigurationError,
    NotImportedError,
)


router = APIRouter(prefix="/api/v1", tags=["PR Collision Atlas API v1"])
T = TypeVar("T")


@router.get("/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    codeql_path = shutil.which("codeql")
    return {
        "status": "ok",
        "api_version": API_VERSION,
        "database_url_configured": bool(get_database_url()),
        "codeql_available": codeql_path is not None,
        "codeql_path": codeql_path,
        "llm_configured": is_openai_configured(),
        "llm_model": get_openai_model(),
    }


@router.post("/auth/signup", response_model=AuthResponse)
def signup(
    request: AuthRequest,
    service: AuthApiService = Depends(get_auth_service),
) -> dict[str, Any]:
    payload = _call_auth(
        lambda: service.signup(user_id=request.user_id, password=request.password)
    )
    return {"user": payload["user"]}


@router.post("/auth/login", response_model=AuthResponse)
def login(
    request: AuthRequest,
    service: AuthApiService = Depends(get_auth_service),
) -> dict[str, Any]:
    payload = _call_auth(
        lambda: service.login(user_id=request.user_id, password=request.password)
    )
    return {"user": payload["user"]}


@router.post("/auth/logout", response_model=LogoutResponse)
def logout() -> dict[str, str]:
    return {"message": "Logged out."}


@router.get("/auth/me", response_model=AuthResponse)
def me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": current_user}


@router.get("/repositories", response_model=RepositoryListResponse)
def list_repositories(
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(
        lambda: service.list_repositories(
            limit=limit,
            offset=offset,
            query=query,
        )
    )


@router.post("/repositories", response_model=RepositoryImportResponse)
def create_repository(
    request: RepositoryImportRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(lambda: service.create_repository(request))


@router.get("/repositories/{owner}/{repo}", response_model=RepositoryDetailResponse)
def get_repository(
    owner: str,
    repo: str,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(lambda: service.get_repository(owner=owner, repo=repo))


@router.patch("/repositories/{owner}/{repo}", response_model=RepositoryImportResponse)
def refresh_repository(
    owner: str,
    repo: str,
    request: RepositoryImportRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(
        lambda: service.refresh_repository(
            owner=owner,
            repo=repo,
            request=request,
        )
    )


@router.delete("/repositories/{owner}/{repo}")
def delete_repository(
    owner: str,
    repo: str,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(lambda: service.delete_repository(owner=owner, repo=repo))


@router.get(
    "/repositories/{owner}/{repo}/pull-requests",
    response_model=PullRequestListResponse,
)
def list_pull_requests(
    owner: str,
    repo: str,
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(
        lambda: service.list_pull_requests(
            owner=owner,
            repo=repo,
            state=state,
            limit=limit,
            offset=offset,
            query=query,
        )
    )


@router.get("/repositories/{owner}/{repo}/atlas", response_model=AtlasResponse)
def load_atlas(
    owner: str,
    repo: str,
    prs: str = Query(..., min_length=1),
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    pr_numbers = _parse_pr_numbers(prs)
    return _call_service(
        lambda: service.load_atlas(
            owner=owner,
            repo=repo,
            pr_numbers=pr_numbers,
        )
    )


@router.post("/analysis", response_model=AnalysisOutputResponse)
def run_analysis(
    request: AnalysisRunRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(lambda: service.run_analysis(request))


@router.post("/analysis/jobs", response_model=AnalysisJobStartResponse)
def start_analysis_job(
    request: AnalysisRunRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return _call_service(lambda: analysis_job_manager.start(request))


@router.get("/analysis/jobs/{job_id}", response_model=AnalysisJobStatusResponse)
def get_analysis_job(
    job_id: str,
    _current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return _call_service(lambda: analysis_job_manager.get(job_id))


@router.post("/ai-agent/messages", response_model=AiAgentMessageResponse)
def ai_agent_message(
    request: AiAgentMessageRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AiAgentService = Depends(get_ai_agent_service),
) -> AiAgentMessageResponse:
    return _call_service(lambda: service.respond(request))


@router.get(
    "/repositories/{owner}/{repo}/pull-requests/{pr_number}/files/{file_path_id}/comments",
    response_model=CommentListResponse,
)
def list_comments(
    owner: str,
    repo: str,
    pr_number: int,
    file_path_id: int,
    _current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(
        lambda: service.list_comments(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            file_path_id=file_path_id,
        )
    )


@router.post(
    "/repositories/{owner}/{repo}/pull-requests/{pr_number}/files/{file_path_id}/comments",
    response_model=CommentResponse,
)
def create_comment(
    owner: str,
    repo: str,
    pr_number: int,
    file_path_id: int,
    request: CommentCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    service: AtlasApiService = Depends(get_api_service),
) -> dict[str, Any]:
    return _call_service(
        lambda: service.create_comment(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            file_path_id=file_path_id,
            author_user_id=int(current_user["id"]),
            body=request.body,
        )
    )


def _parse_pr_numbers(value: str) -> tuple[int, ...]:
    try:
        numbers = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="prs must contain comma-separated positive integers.",
        ) from exc
    if not numbers or any(number < 1 for number in numbers):
        raise HTTPException(
            status_code=422,
            detail="prs must contain comma-separated positive integers.",
        )
    return numbers


def _call_service(action: Callable[[], T]) -> T:
    try:
        return action()
    except DuplicateRepositoryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GitHubImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except NotImportedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnalysisJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable or credentials are invalid.",
        ) from exc


def _call_auth(action: Callable[[], T]) -> T:
    try:
        return action()
    except DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable or credentials are invalid.",
        ) from exc
