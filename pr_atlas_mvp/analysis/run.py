#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pr_atlas_mvp.analysis.models import (
    AnalysisRequest,
    CODEQL_QUERY_PROFILES,
    DEFAULT_CODEQL_QUERY_PROFILE,
    DEFAULT_QUERY_PACK_VERSION,
)
from pr_atlas_mvp.analysis.pipeline import run_analysis
from pr_atlas_mvp.postgres.connection import connect_database


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PR Collision Atlas CodeQL-backed analysis.",
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. python")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. cpython")
    parser.add_argument(
        "--prs",
        required=True,
        help="Comma-separated PR numbers already imported into PostgreSQL.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="PostgreSQL URL. Defaults to DATABASE_URL from environment or .env.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Local checkout used for CodeQL DB creation and validation evidence.",
    )
    parser.add_argument(
        "--codeql-db",
        type=Path,
        help="Existing CodeQL database path. If omitted, --repo-root is used to create one.",
    )
    parser.add_argument(
        "--codeql-results",
        type=Path,
        help="Precomputed CodeQL SARIF/JSON results. Skips CodeQL CLI execution.",
    )
    parser.add_argument(
        "--project-role-map",
        type=Path,
        help="Path to project-role-map.yaml. Defaults to <repo-root>/project-role-map.yaml if present.",
    )
    parser.add_argument(
        "--validation-evidence",
        type=Path,
        help="Optional JSON RepositoryValidationEvidence file.",
    )
    parser.add_argument(
        "--query-pack-version",
        default=DEFAULT_QUERY_PACK_VERSION,
        help="Custom query pack version stored with static cache rows.",
    )
    parser.add_argument(
        "--codeql-query-profile",
        choices=CODEQL_QUERY_PROFILES,
        default=DEFAULT_CODEQL_QUERY_PROFILE,
        help="CodeQL query suite profile to run. Defaults to lite for faster analysis.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write frontend output JSON to this path. Defaults to stdout.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Do not call SQLAlchemy create_all before analysis.",
    )
    args = parser.parse_args()
    validate_args(parser, args)
    return args


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    try:
        parse_pr_numbers(args.prs)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.database_url.strip():
        parser.error("DATABASE_URL is required.")
    if args.codeql_results is None and args.codeql_db is None and args.repo_root is None:
        parser.error("Provide --codeql-results, --codeql-db, or --repo-root.")


def parse_pr_numbers(value: str) -> tuple[int, ...]:
    try:
        numbers = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("--prs must contain comma-separated integers.") from exc
    if not numbers:
        raise ValueError("--prs must include at least one PR number.")
    if any(number < 1 for number in numbers):
        raise ValueError("PR numbers must be positive.")
    return numbers


def build_request(args: argparse.Namespace) -> AnalysisRequest:
    role_map = args.project_role_map
    if role_map is None and args.repo_root is not None:
        candidate = args.repo_root / "project-role-map.yaml"
        role_map = candidate if candidate.exists() else None
    return AnalysisRequest(
        owner=args.owner,
        repo=args.repo,
        pr_numbers=parse_pr_numbers(args.prs),
        database_url=args.database_url,
        repo_root=args.repo_root,
        codeql_db=args.codeql_db,
        codeql_results=args.codeql_results,
        project_role_map=role_map,
        validation_evidence=args.validation_evidence,
        output=args.output,
        query_pack_version=args.query_pack_version,
        codeql_query_profile=args.codeql_query_profile,
        create_schema=not args.skip_schema,
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    request = build_request(args)
    with connect_database(args.database_url) as session:
        state = run_analysis(session, request)
        session.commit()

    payload: dict[str, Any] = state.outputs
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output is None:
        print(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Analysis output written: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nAnalysis interrupted.")
