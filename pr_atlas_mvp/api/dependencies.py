from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pr_atlas_mvp.analysis.models import AnalysisRequest, AnalysisState
from pr_atlas_mvp.analysis.pipeline import run_analysis
from pr_atlas_mvp.ai_agent import AiAgentService
from pr_atlas_mvp.api.config import get_database_url
from pr_atlas_mvp.api.services import AuthApiService, AuthError, AtlasApiService
from pr_atlas_mvp.postgres.connection import connect_database


AnalysisRunner = Callable[[Session, AnalysisRequest], AnalysisState]


def get_session() -> Iterator[Session]:
    database_url = get_database_url()
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not configured.",
        )
    try:
        session = connect_database(database_url)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable or credentials are invalid.",
        ) from exc
    try:
        yield session
    finally:
        session.close()


def get_analysis_runner() -> AnalysisRunner:
    return run_analysis


def get_auth_service(session: Session = Depends(get_session)) -> AuthApiService:
    return AuthApiService(session=session)


def get_current_user(request: Request) -> dict[str, object]:
    user_id, password = _parse_basic_auth(request.headers.get("Authorization", ""))
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    database_url = get_database_url()
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not configured.",
        )
    try:
        with connect_database(database_url) as session:
            return AuthApiService(session=session).current_user(
                user_id=user_id,
                password=password,
            )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable or credentials are invalid.",
        ) from exc


def get_api_service(
    session: Session = Depends(get_session),
    runner: AnalysisRunner = Depends(get_analysis_runner),
) -> AtlasApiService:
    return AtlasApiService(session=session, runner=runner)


def get_ai_agent_service() -> AiAgentService:
    return AiAgentService()


def _parse_basic_auth(header: str) -> tuple[str, str]:
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic" or not value.strip():
        return "", ""
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return "", ""
    user_id, separator, password = decoded.partition(":")
    if not separator or not user_id:
        return "", ""
    return user_id, password
