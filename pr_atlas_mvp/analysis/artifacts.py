from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RepositoryArtifactPaths:
    root: Path
    repo: Path
    worktrees: Path
    codeql_dbs: Path
    codeql_results: Path


@dataclass(frozen=True)
class PullRequestArtifactPaths:
    repository: RepositoryArtifactPaths
    worktree: Path
    codeql_db: Path
    codeql_results: Path


def artifact_root() -> Path:
    configured = os.environ.get("PR_ATLAS_ARTIFACT_ROOT", "").strip()
    return Path(configured).expanduser() if configured else PROJECT_ROOT / ".atlas"


def repository_artifact_paths(owner: str, repo: str) -> RepositoryArtifactPaths:
    owner_part = safe_path_component(owner)
    repo_part = safe_path_component(repo)
    root = artifact_root()
    return RepositoryArtifactPaths(
        root=root,
        repo=root / "repos" / owner_part / repo_part,
        worktrees=root / "worktrees" / owner_part / repo_part,
        codeql_dbs=root / "codeql-dbs" / owner_part / repo_part,
        codeql_results=root / "codeql-results" / owner_part / repo_part,
    )


def pull_request_artifact_paths(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    query_pack_version: str,
    codeql_query_profile: str = "lite",
) -> PullRequestArtifactPaths:
    repository = repository_artifact_paths(owner, repo)
    commit_part = safe_path_component(head_sha)
    version_part = safe_path_component(query_pack_version)
    profile_part = safe_path_component(codeql_query_profile)
    return PullRequestArtifactPaths(
        repository=repository,
        worktree=repository.worktrees / f"pr-{pr_number}-{commit_part[:12]}",
        codeql_db=repository.codeql_dbs / commit_part / version_part,
        codeql_results=repository.codeql_results / commit_part / version_part / profile_part / "results.sarif",
    )


def repository_artifact_status(owner: str, repo: str) -> dict[str, str | bool]:
    paths = repository_artifact_paths(owner, repo)
    return {
        "artifact_root": str(paths.root),
        "repo_checkout_exists": paths.repo.exists(),
        "worktrees_exist": paths.worktrees.exists(),
        "codeql_dbs_exist": paths.codeql_dbs.exists(),
        "codeql_results_exist": paths.codeql_results.exists(),
    }


def ensure_repository_checkout(owner: str, repo: str) -> Path:
    paths = repository_artifact_paths(owner, repo)
    clone_url = f"https://github.com/{owner}/{repo}.git"
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("PATH에서 git CLI를 찾을 수 없습니다.")

    if (paths.repo / ".git").exists():
        _run([git_path, "-C", str(paths.repo), "fetch", "--all", "--prune"])
        return paths.repo

    if paths.repo.exists():
        raise RuntimeError(f"산출물 경로가 이미 있지만 git checkout이 아닙니다: {paths.repo}")

    paths.repo.parent.mkdir(parents=True, exist_ok=True)
    _run([git_path, "clone", clone_url, str(paths.repo)])
    return paths.repo


def ensure_worktree(repo_path: Path, worktree_path: Path, commit_sha: str) -> Path:
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("PATH에서 git CLI를 찾을 수 없습니다.")

    if (worktree_path / ".git").exists():
        current_sha = _run(
            [git_path, "-C", str(worktree_path), "rev-parse", "HEAD"],
        ).strip()
        if current_sha == commit_sha:
            return worktree_path
        shutil.rmtree(worktree_path)
    elif worktree_path.exists():
        shutil.rmtree(worktree_path)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _run([git_path, "-C", str(repo_path), "fetch", "origin", commit_sha])
    _run([git_path, "-C", str(repo_path), "worktree", "prune"])
    _run(
        [
            git_path,
            "-C",
            str(repo_path),
            "worktree",
            "add",
            "--detach",
            "--force",
            str(worktree_path),
            commit_sha,
        ]
    )
    return worktree_path


def remove_repository_artifacts(owner: str, repo: str) -> list[str]:
    paths = repository_artifact_paths(owner, repo)
    removed: list[str] = []
    for path in (paths.repo, paths.worktrees, paths.codeql_dbs, paths.codeql_results):
        if path.exists():
            shutil.rmtree(path)
            removed.append(str(path))
    return removed


def safe_path_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    if not normalized:
        raise ValueError("Path component cannot be empty.")
    return normalized[:120]


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout
