from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import patch

from pr_atlas_mvp.analysis.models import (
    AnalysisRequest,
    CodeQLEvidence,
    CodeQLSnapshotInfo,
    FileChangeInfo,
    ProjectRoleMap,
    PullRequestInfo,
    RagDocument,
    RiskFileFinding,
    SourceContext,
)
from pr_atlas_mvp.analysis.langchain_adapters import generate_intent_and_explanations
from pr_atlas_mvp.analysis.pipeline import run_analysis


class AnalysisPipelineTests(unittest.TestCase):
    def test_langgraph_pipeline_preserves_analysis_output_contract(self) -> None:
        context = _context()
        request = AnalysisRequest(
            owner="python",
            repo="cpython",
            pr_numbers=(123,),
            create_schema=False,
        )
        codeql = CodeQLEvidence(
            snapshot=CodeQLSnapshotInfo(
                id=None,
                repository_id=1,
                commit_sha="head",
                codeql_database_uri="/atlas/codeql-dbs/python/cpython/head/pr-impact-v1",
                query_pack_version="pr-impact-v1",
                status="failed",
            ),
            changes=(),
            findings=(),
            errors=("PATH에서 CodeQL CLI를 찾을 수 없습니다.",),
        )
        outputs = {
            "canvas_layout": {"nodes": [], "edges": []},
            "pr_overlay": {"pull_requests": []},
            "risk_analysis": {"files": [], "errors": []},
            "merge_recommendation": {"recommended_order": []},
            "file_details": {},
        }

        with (
            patch("pr_atlas_mvp.analysis.pipeline.load_source_context", return_value=context),
            patch(
                "pr_atlas_mvp.analysis.pipeline.build_rag_documents",
                return_value=(_rag_document(),),
            ),
            patch(
                "pr_atlas_mvp.analysis.pipeline.load_project_role_map",
                return_value=ProjectRoleMap(version=1, roles=(), is_default=True),
            ),
            patch(
                "pr_atlas_mvp.analysis.pipeline.load_or_run_codeql_analysis",
                return_value=codeql,
            ),
            patch(
                "pr_atlas_mvp.analysis.pipeline.upsert_static_analysis_snapshot",
                return_value=_SnapshotRow(),
            ),
            patch("pr_atlas_mvp.analysis.pipeline.replace_static_evidence") as replace_static,
            patch(
                "pr_atlas_mvp.analysis.pipeline.collect_validation_signals",
                return_value=(),
            ),
            patch(
                "pr_atlas_mvp.analysis.pipeline.compute_deterministic_risk",
                return_value=(),
            ),
            patch(
                "pr_atlas_mvp.analysis.pipeline.score_project_impact",
                return_value=(_risk_finding(),),
            ),
            patch(
                "pr_atlas_mvp.analysis.pipeline.serialize_outputs",
                return_value=outputs,
            ),
        ):
            state = run_analysis(_FakeSession(), request)

        self.assertEqual(sorted(state.outputs), [
            "canvas_layout",
            "file_details",
            "llm_analysis",
            "merge_recommendation",
            "pr_overlay",
            "risk_analysis",
        ])
        self.assertEqual(state.source_context, context)
        self.assertEqual(state.rag_documents[0].document_id, "repository:1")
        self.assertEqual(state.langchain_documents[0].page_content, "supporting context")
        self.assertFalse(state.llm_analysis["enabled"])
        replace_static.assert_called_once()

    def test_openai_llm_adapter_uses_structured_output_without_changing_risk(self) -> None:
        output = {
            "change_intent": "요청 처리 경로를 정리합니다.",
            "review_focus": ["공개 API 동작 확인"],
            "summary": "LLM이 근거 기반 설명을 생성했습니다.",
            "file_explanations": [
                {
                    "file_path_id": 30,
                    "file_path": "src/pkg/client.py",
                    "explanation": "공개 API 주변 변경입니다.",
                    "review_focus": ["호환성 확인"],
                }
            ],
            "merge_notes": ["위험 점수는 deterministic 결과를 따릅니다."],
        }

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch(
                "pr_atlas_mvp.analysis.langchain_adapters._create_openai_response",
                return_value={"output_text": json.dumps(output, ensure_ascii=False)},
            ) as create_response,
        ):
            result = generate_intent_and_explanations(
                risk_findings=(_risk_finding(),),
                langchain_documents=(),
                use_llm=True,
                model="gpt-test",
                timeout_seconds=3,
            )

        self.assertTrue(result["enabled"])
        self.assertEqual(result["model"], "gpt-test")
        self.assertEqual(result["summary"], "LLM이 근거 기반 설명을 생성했습니다.")
        self.assertEqual(result["report"]["file_explanations"][0]["file_path_id"], 30)
        create_response.assert_called_once()


class _SnapshotRow:
    id = 99


class _FakeNestedTransaction:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class _FakeSession:
    def begin_nested(self) -> _FakeNestedTransaction:
        return _FakeNestedTransaction()


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
                id=20,
                pull_request_id=10,
                pr_number=123,
                file_path_id=30,
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


def _rag_document() -> RagDocument:
    return RagDocument(
        document_id="repository:1",
        document_type="repository_summary",
        repository_id=1,
        pull_request_id=None,
        file_path_id=None,
        path=None,
        title="python/cpython",
        content="supporting context",
    )


def _risk_finding() -> RiskFileFinding:
    return RiskFileFinding(
        file_path_id=30,
        path="src/pkg/client.py",
        node_id="file:30",
        score=20,
        risk_level="medium",
        public_surface_level="internal",
        related_prs=(123,),
        reasons=("기본 위험 근거입니다.",),
        evidence=(),
        static_impact_paths=(),
        affected_project_roles=(),
        validation_signals=(),
        documentation_context=(),
        uncertainty_signals=(),
        codeql_queries=(),
    )


if __name__ == "__main__":
    unittest.main()
