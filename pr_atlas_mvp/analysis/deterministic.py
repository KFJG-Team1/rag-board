from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from pr_atlas_mvp.analysis.models import (
    DeterministicFileRisk,
    FileChangeInfo,
    HunkInfo,
    SourceContext,
)


PATH_CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("migration", ("migration", "migrations", "schema", ".sql")),
    ("config", (".env", "config", "deploy", "docker", "k8s", ".yaml", ".yml", ".toml")),
    ("auth", ("auth", "login", "permission", "token", "session")),
    ("api", ("api", "controller", "route", "schema", "response", "request")),
    ("dependency", ("lock", "package-lock", "yarn.lock", "pnpm-lock", "requirements")),
    ("docs", ("readme", "docs/", ".md", ".rst")),
    ("test", ("test", "tests/", "spec", "snapshot")),
)


def classify_path(path: str) -> tuple[str, ...]:
    normalized = path.lower()
    categories: list[str] = []
    for category, patterns in PATH_CATEGORY_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            categories.append(category)
    if not categories:
        categories.append("code")
    return tuple(dict.fromkeys(categories))


def compute_deterministic_risk(context: SourceContext) -> tuple[DeterministicFileRisk, ...]:
    changes_by_file: dict[int, list[FileChangeInfo]] = defaultdict(list)
    hunks_by_file: dict[int, list[HunkInfo]] = defaultdict(list)

    for change in context.file_changes:
        changes_by_file[change.file_path_id].append(change)
    for hunk in context.hunks:
        hunks_by_file[hunk.file_path_id].append(hunk)

    findings: list[DeterministicFileRisk] = []
    for file_path_id, changes in sorted(
        changes_by_file.items(), key=lambda item: min(change.path for change in item[1])
    ):
        path = changes[0].path
        categories = classify_path(path)
        related_prs = tuple(sorted({change.pr_number for change in changes}))
        score = 0
        reasons: list[str] = []
        conflict_points: list[dict[str, object]] = []

        if len(related_prs) > 1:
            score += 15
            reasons.append(f"선택한 PR {len(related_prs)}개가 같은 파일을 수정합니다.")

        total_changes = sum(change.changes for change in changes)
        if total_changes >= 200:
            score += 10
            reasons.append("이 파일의 변경량이 큽니다.")
        elif total_changes >= 50:
            score += 5
            reasons.append("이 파일의 변경량이 중간 수준입니다.")

        category_score, category_reasons = _score_categories(categories)
        score += category_score
        reasons.extend(category_reasons)

        hunk_score, hunk_reasons, hunk_conflicts = _score_hunks(hunks_by_file[file_path_id])
        score += hunk_score
        reasons.extend(hunk_reasons)
        conflict_points.extend(hunk_conflicts)

        if not reasons:
            reasons.append("명확한 충돌 신호가 없는 단일 파일 변경입니다.")

        findings.append(
            DeterministicFileRisk(
                file_path_id=file_path_id,
                path=path,
                related_prs=related_prs,
                score=max(score, 0),
                reasons=tuple(dict.fromkeys(reasons)),
                categories=categories,
                conflict_points=tuple(conflict_points),
            )
        )

    return tuple(findings)


def hunk_ranges_overlap(left: HunkInfo, right: HunkInfo) -> bool:
    return left.new_start < right.new_end and right.new_start < left.new_end


def hunk_distance(left: HunkInfo, right: HunkInfo) -> int:
    if hunk_ranges_overlap(left, right):
        return 0
    return min(abs(left.new_end - right.new_start), abs(right.new_end - left.new_start))


def _score_categories(categories: tuple[str, ...]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if any(category in categories for category in ("migration", "config", "dependency")):
        score += 15
        reasons.append("설정, 의존성, 마이그레이션 경로는 검토가 필요합니다.")
    if "auth" in categories:
        score += 12
        reasons.append("인증/세션 관련 경로라 정확성과 보안 검토가 필요합니다.")
    if "api" in categories:
        score += 10
        reasons.append("API 성격의 경로라 호출자 호환성에 영향을 줄 수 있습니다.")
    if "test" in categories:
        score += 3
        reasons.append("테스트 경로가 변경되어 검증 맥락으로 확인해야 합니다.")
    if "docs" in categories and set(categories).issubset({"docs"}):
        reasons.append("문서 전용 경로는 정적 영향 근거가 없으면 낮은 위험으로 봅니다.")
    return score, reasons


def _score_hunks(hunks: list[HunkInfo]) -> tuple[int, list[str], list[dict[str, object]]]:
    score = 0
    reasons: list[str] = []
    conflicts: list[dict[str, object]] = []
    pair_scores: list[int] = []

    for left, right in combinations(hunks, 2):
        if left.pull_request_id == right.pull_request_id:
            continue
        distance = hunk_distance(left, right)
        if distance == 0:
            pair_score = 35
            reason = "선택한 PR들이 같은 파일의 겹치는 hunk를 수정합니다."
            kind = "hunk_overlap"
        elif distance <= 20:
            pair_score = 20
            reason = "선택한 PR들이 20줄 이내의 가까운 hunk를 수정합니다."
            kind = "near_hunk"
        elif distance <= 80:
            pair_score = 10
            reason = "선택한 PR들이 같은 파일의 80줄 이내 영역을 수정합니다."
            kind = "same_file_proximity"
        else:
            pair_score = 3
            reason = "선택한 PR들이 같은 파일의 떨어진 hunk를 수정합니다."
            kind = "weak_same_file"

        pair_scores.append(pair_score)
        reasons.append(reason)
        conflicts.append(
            {
                "type": kind,
                "left_pr": left.pr_number,
                "right_pr": right.pr_number,
                "left_hunk_id": left.id,
                "right_hunk_id": right.id,
                "distance": distance,
                "path": left.path,
            }
        )

    if pair_scores:
        score += max(pair_scores)
        if len(pair_scores) > 1:
            score += min(10, len(pair_scores) * 2)

    return score, list(dict.fromkeys(reasons)), conflicts
