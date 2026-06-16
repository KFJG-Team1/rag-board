from __future__ import annotations

import unittest

from pr_atlas_mvp.analysis.models import (
    FileChangeInfo,
    PullRequestInfo,
    RiskFileFinding,
    RoleMatch,
    SourceContext,
)
from pr_atlas_mvp.analysis.serializers import (
    serialize_canvas_layout,
    serialize_file_detail,
    serialize_merge_recommendation,
    serialize_risk_analysis,
)


class AnalysisSerializerTests(unittest.TestCase):
    def test_canvas_layout_positions_project_roles_in_separate_lane(self) -> None:
        context = _context()
        findings = (_risk_finding(),)

        payload = serialize_canvas_layout(context, findings)
        nodes = {node["id"]: node for node in payload["nodes"]}

        self.assertIn("file:20", nodes)
        self.assertIn("role:public_api", nodes)
        self.assertEqual(nodes["role:public_api"]["node_type"], "project_role")
        self.assertGreaterEqual(nodes["role:public_api"]["x"], 900)
        self.assertNotEqual(
            (nodes["file:20"]["x"], nodes["file:20"]["y"]),
            (nodes["role:public_api"]["x"], nodes["role:public_api"]["y"]),
        )

    def test_human_readable_analysis_output_is_korean(self) -> None:
        context = _context()
        findings = (_risk_finding(),)

        risk = serialize_risk_analysis(
            context,
            findings,
            ("PATH에서 CodeQL CLI를 찾을 수 없습니다.",),
            codeql_metadata={"query_profile": "lite", "label": "빠른 CodeQL-lite 분석 결과"},
        )
        merge = serialize_merge_recommendation(context, findings)
        detail = serialize_file_detail(context, findings[0])

        self.assertIn("가장 위험한 파일", risk["summary"])
        self.assertEqual(risk["codeql"]["query_profile"], "lite")
        self.assertIn("CodeQL-lite", risk["codeql"]["label"])
        self.assertIn("영향 점수가 높은 PR", merge["recommended_order"][0]["reason"])
        self.assertIn("LLM 보고는 비활성화", merge["llm_summary"])
        self.assertIn("RAG 문서는 보조 맥락", detail["rag_explanation"]["summary"])


def _context() -> SourceContext:
    return SourceContext(
        repository_id=1,
        repo_key="python/cpython",
        owner="python",
        repo="cpython",
        pull_requests=(
            PullRequestInfo(
                id=10,
                number=123,
                title="Example PR",
                url="https://example.test/pr/123",
                state="open",
                base_ref="main",
                head_ref="feature",
                base_sha="base",
                head_sha="head",
                labels=("api",),
            ),
        ),
        file_changes=(
            FileChangeInfo(
                id=30,
                pull_request_id=10,
                pr_number=123,
                file_path_id=20,
                path="src/pkg/client.py",
                status="modified",
                additions=4,
                deletions=1,
                changes=5,
                patch=None,
            ),
        ),
        hunks=(),
    )


def _risk_finding() -> RiskFileFinding:
    return RiskFileFinding(
        file_path_id=20,
        path="src/pkg/client.py",
        node_id="file:20",
        score=68,
        risk_level="high",
        public_surface_level="public",
        related_prs=(123,),
        reasons=("CodeQL이 공개 표면 영향을 찾았습니다.",),
        evidence=({"reason": "CodeQL public_surface 근거입니다."},),
        static_impact_paths=(),
        affected_project_roles=(
            RoleMatch(
                role_id="public_api",
                name="공개 API",
                criticality="important",
                match_reason="심볼이 공개 API와 일치합니다",
            ),
        ),
        validation_signals=(),
        documentation_context=(),
        uncertainty_signals=(),
        codeql_queries=(),
    )


if __name__ == "__main__":
    unittest.main()
