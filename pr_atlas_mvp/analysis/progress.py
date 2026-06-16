from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


ProgressReporter = Callable[[dict[str, Any]], None]
_current_reporter: ContextVar[ProgressReporter | None] = ContextVar(
    "pr_atlas_progress_reporter",
    default=None,
)


@contextmanager
def progress_reporter(reporter: ProgressReporter | None) -> Iterator[None]:
    token = _current_reporter.set(reporter)
    try:
        yield
    finally:
        _current_reporter.reset(token)


def emit_progress(
    stage: str,
    message: str,
    *,
    percent: int | None = None,
    pr_number: int | None = None,
    status: str = "running",
) -> None:
    reporter = _current_reporter.get()
    if reporter is None:
        return
    event: dict[str, Any] = {
            "stage": stage,
            "message": message,
            "status": status,
    }
    if percent is not None:
        event["percent"] = max(0, min(100, percent))
    if pr_number is not None:
        event["pr_number"] = pr_number
    reporter(event)
