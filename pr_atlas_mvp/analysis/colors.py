from __future__ import annotations


PR_COLORS = (
    "#1d4ed8",
    "#dc2626",
    "#16a34a",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#be123c",
    "#65a30d",
    "#c026d3",
    "#0f766e",
    "#92400e",
    "#475569",
)


def color_for_pr_number(number: int) -> str:
    return PR_COLORS[(max(1, number) - 1) % len(PR_COLORS)]


def color_for_pr_index(index: int) -> str:
    return PR_COLORS[max(0, index) % len(PR_COLORS)]
