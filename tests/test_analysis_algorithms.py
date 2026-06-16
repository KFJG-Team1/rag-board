from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pr_atlas_mvp.analysis.codeql_parser import (
    normalize_codeql_results,
    parse_codeql_results,
)
from pr_atlas_mvp.analysis.codeql_runner import (
    build_codeql_analyze_command,
    build_codeql_base_command,
    load_or_run_codeql_analysis,
)
from pr_atlas_mvp.analysis.deterministic import compute_deterministic_risk
from pr_atlas_mvp.analysis.models import (
    AnalysisRequest,
    CodeQLEvidence,
    CodeQLSnapshotInfo,
    FileChangeInfo,
    HunkInfo,
    PullRequestInfo,
    SourceContext,
)
from pr_atlas_mvp.analysis.role_map import load_project_role_map, match_roles_for_file
from pr_atlas_mvp.analysis.scoring import score_project_impact


class AnalysisAlgorithmTests(unittest.TestCase):
    def test_deterministic_hunk_overlap_scores_same_file_collision(self) -> None:
        context = _source_context(
            files=(
                _file_change(101, 1, 10, 501, "src/pkg/client.py"),
                _file_change(102, 2, 11, 501, "src/pkg/client.py"),
            ),
            hunks=(
                _hunk(201, 101, 1, 10, 501, "src/pkg/client.py", 40, 12),
                _hunk(202, 102, 2, 11, 501, "src/pkg/client.py", 45, 8),
            ),
        )

        findings = compute_deterministic_risk(context)

        self.assertEqual(len(findings), 1)
        self.assertGreaterEqual(findings[0].score, 50)
        self.assertEqual(findings[0].conflict_points[0]["type"], "hunk_overlap")

    def test_codeql_sarif_symbol_maps_to_changed_hunk(self) -> None:
        context = _source_context(
            files=(_file_change(101, 1, 10, 501, "src/pkg/client.py"),),
            hunks=(_hunk(201, 101, 1, 10, 501, "src/pkg/client.py", 42, 10),),
        )
        sarif = {
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "rules": [
                                {
                                    "id": "pr-impact/symbol-definitions",
                                    "properties": {"queryVersion": "v1"},
                                }
                            ]
                        }
                    },
                    "results": [
                        {
                            "ruleId": "pr-impact/symbol-definitions",
                            "message": {
                                "text": (
                                    'pr_atlas:{"record_type":"symbol_definition",'
                                    '"symbol_kind":"method",'
                                    '"symbol_name":"pkg.client.Client.request"}'
                                )
                            },
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {
                                            "uri": "src/pkg/client.py"
                                        },
                                        "region": {
                                            "startLine": 40,
                                            "endLine": 60,
                                        },
                                    }
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.sarif"
            path.write_text(json.dumps(sarif), encoding="utf-8")
            raw_results = parse_codeql_results(path, "fallback-v1")

        changes, findings = normalize_codeql_results(raw_results, context)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].hunk_id, 201)
        self.assertEqual(changes[0].symbol_name, "pkg.client.Client.request")
        self.assertEqual(findings, ())

    def test_role_map_matches_public_api_symbol(self) -> None:
        role_map_text = """
version: 1
roles:
  - role_id: public_api
    name: Public API
    criticality: core
    paths:
      - src/pkg/client.py
    public_api:
      - pkg.client.Client.request
    risk_tags:
      - backwards_compatibility
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "project-role-map.yaml"
            path.write_text(role_map_text, encoding="utf-8")
            role_map = load_project_role_map(path)

        matches = match_roles_for_file(
            "src/pkg/client.py",
            role_map=role_map,
            symbol_names=("pkg.client.Client.request",),
        )

        self.assertEqual(matches[0].role_id, "public_api")
        self.assertEqual(matches[0].criticality, "core")

    def test_scoring_keeps_codeql_failure_as_uncertainty(self) -> None:
        context = _source_context(
            files=(_file_change(101, 1, 10, 501, "src/pkg/client.py"),),
            hunks=(_hunk(201, 101, 1, 10, 501, "src/pkg/client.py", 42, 10),),
        )
        deterministic = compute_deterministic_risk(context)
        role_map = load_project_role_map(None)
        codeql = CodeQLEvidence(
            snapshot=CodeQLSnapshotInfo(
                id=None,
                repository_id=1,
                commit_sha="abc",
                codeql_database_uri="",
                query_pack_version="v1",
                status="failed",
            ),
            changes=(),
            findings=(),
            errors=("CodeQL CLI is not available on PATH.",),
        )

        scored = score_project_impact(
            context=context,
            deterministic_findings=deterministic,
            codeql_evidence=codeql,
            role_map=role_map,
            validation_signals=(),
        )

        self.assertEqual(len(scored), 1)
        self.assertIn("CodeQL 정적 영향 분석을 사용할 수 없어", scored[0].uncertainty_signals[0])

    def test_codeql_analyze_command_uses_local_query_pack(self) -> None:
        command = build_codeql_analyze_command(
            codeql_path="/usr/local/bin/codeql",
            database_path=Path("/tmp/db"),
            output_path=Path("/tmp/results.sarif"),
        )

        self.assertNotIn("--download", command)
        self.assertIn("pr-impact-lite.qls", " ".join(command))

    def test_codeql_analyze_command_can_use_full_query_suite(self) -> None:
        command = build_codeql_analyze_command(
            codeql_path="/usr/local/bin/codeql",
            database_path=Path("/tmp/db"),
            output_path=Path("/tmp/results.sarif"),
            codeql_query_profile="full",
        )

        joined = " ".join(command)
        self.assertIn("pr-impact.qls", joined)
        self.assertNotIn("pr-impact-lite.qls", joined)

    def test_codeql_lite_suite_excludes_test_relation_query(self) -> None:
        suite = Path("codeql/pr-impact/codeql-suites/pr-impact-lite.qls").read_text()

        self.assertIn("SymbolDefinitions.ql", suite)
        self.assertIn("ClassDefinitions.ql", suite)
        self.assertIn("PublicSurface.ql", suite)
        self.assertIn("PublicSurfaceClasses.ql", suite)
        self.assertNotIn("TestRelations.ql", suite)

    def test_lite_results_without_test_relation_stay_ready(self) -> None:
        context = _source_context(files=(), hunks=())
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.json"
            results_path.write_text("[]", encoding="utf-8")

            evidence = load_or_run_codeql_analysis(
                AnalysisRequest(
                    owner="owner",
                    repo="repo",
                    pr_numbers=(10,),
                    codeql_results=results_path,
                    codeql_query_profile="lite",
                ),
                context,
            )

        self.assertEqual(evidence.snapshot.status, "ready")
        self.assertEqual(evidence.snapshot.metadata["codeql_query_profile"], "lite")

    def test_codeql_uses_rosetta_by_default_on_darwin_arm64(self) -> None:
        command = build_codeql_base_command(
            "/opt/homebrew/bin/codeql",
            platform_name="darwin",
            machine_name="arm64",
        )

        self.assertEqual(
            command,
            ["/usr/bin/arch", "-x86_64", "/opt/homebrew/bin/codeql"],
        )


def _source_context(
    *,
    files: tuple[FileChangeInfo, ...],
    hunks: tuple[HunkInfo, ...],
) -> SourceContext:
    return SourceContext(
        repository_id=1,
        repo_key="repo-key",
        owner="owner",
        repo="repo",
        pull_requests=(
            PullRequestInfo(
                id=1,
                number=10,
                title="First PR",
                url="https://example.test/1",
                state="open",
                base_ref="main",
                head_ref="feature-a",
                base_sha="base",
                head_sha="head-a",
                labels=(),
            ),
            PullRequestInfo(
                id=2,
                number=11,
                title="Second PR",
                url="https://example.test/2",
                state="open",
                base_ref="main",
                head_ref="feature-b",
                base_sha="base",
                head_sha="head-b",
                labels=(),
            ),
        ),
        file_changes=files,
        hunks=hunks,
    )


def _file_change(
    row_id: int,
    pull_request_id: int,
    pr_number: int,
    file_path_id: int,
    path: str,
) -> FileChangeInfo:
    return FileChangeInfo(
        id=row_id,
        pull_request_id=pull_request_id,
        pr_number=pr_number,
        file_path_id=file_path_id,
        path=path,
        status="modified",
        additions=5,
        deletions=2,
        changes=7,
        patch="@@" ,
    )


def _hunk(
    row_id: int,
    pr_file_id: int,
    pull_request_id: int,
    pr_number: int,
    file_path_id: int,
    path: str,
    new_start: int,
    new_lines: int,
) -> HunkInfo:
    return HunkInfo(
        id=row_id,
        pr_file_id=pr_file_id,
        pull_request_id=pull_request_id,
        pr_number=pr_number,
        file_path_id=file_path_id,
        path=path,
        hunk_index=1,
        old_start=new_start,
        old_lines=new_lines,
        new_start=new_start,
        new_lines=new_lines,
        header="@@",
        hunk_json={"lines": []},
    )


if __name__ == "__main__":
    unittest.main()
