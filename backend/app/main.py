from fastapi import FastAPI

from app.db import create_tables
from app.routers.ingest import router as ingest_router


app = FastAPI(title="Corporate Memory Skeleton")


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ingest_router)
