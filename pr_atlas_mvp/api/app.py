from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pr_atlas_mvp.api.config import ALLOWED_ORIGINS, load_local_env
from pr_atlas_mvp.api.routes import router


def create_app() -> FastAPI:
    load_local_env()
    fastapi_app = FastAPI(
        title="PR Collision Atlas API",
        version="0.1.0",
    )
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_app.include_router(router)
    return fastapi_app


app = create_app()
