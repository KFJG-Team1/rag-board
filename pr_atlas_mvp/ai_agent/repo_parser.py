from __future__ import annotations

import re
from dataclasses import dataclass


OWNER_REPO_RE = re.compile(
    r"(?<![\w.-])(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)(?![\w.-])"
)
GITHUB_URL_RE = re.compile(
    r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
LIMIT_RE = re.compile(r"(?P<limit>\d{1,3})\s*(?:개|prs?|pull\s*requests?)?", re.IGNORECASE)


@dataclass(frozen=True)
class RepositoryRef:
    owner: str
    repo: str

    @property
    def repo_key(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_repository_ref(text: str) -> RepositoryRef | None:
    value = text.strip()
    if not value:
        return None

    match = GITHUB_URL_RE.search(value)
    if match is None:
        match = OWNER_REPO_RE.search(value)
    if match is None:
        return None

    owner = _clean_part(match.group("owner"))
    repo = _clean_part(match.group("repo")).removesuffix(".git")
    if not owner or not repo:
        return None
    return RepositoryRef(owner=owner, repo=repo)


def extract_pr_limit(text: str) -> int | None:
    for match in LIMIT_RE.finditer(text):
        try:
            value = int(match.group("limit"))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _clean_part(value: str) -> str:
    return value.strip().strip("/#?&.,:;\"'()[]{}")
