from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiffLine:
    type: str
    content: str
    old_line: int | None = None
    new_line: int | None = None


@dataclass
class DiffHunk:
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class PullRequestFile:
    path: str
    path_tree: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None
    hunks: list[DiffHunk]
    raw_rest: dict[str, Any]


@dataclass
class PullRequestSnapshot:
    number: int
    title: str
    url: str
    state: str
    base_ref: str
    head_ref: str
    base_sha: str | None
    head_sha: str
    updated_at: str
    labels: list[str]
    files: list[PullRequestFile]
    raw_graphql: dict[str, Any]


@dataclass
class ImportBatch:
    repository: dict[str, str]
    pull_request: PullRequestSnapshot

