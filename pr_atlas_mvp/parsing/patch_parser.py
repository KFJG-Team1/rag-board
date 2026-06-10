from __future__ import annotations

import re

from pr_atlas_mvp.parsing.models import DiffHunk, DiffLine


HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_lines>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_lines>\d+))? @@(?P<section>.*)$"
)


def parse_patch(patch: str | None) -> list[DiffHunk]:
    if not patch:
        return []

    hunks: list[DiffHunk] = []
    current: DiffHunk | None = None
    old_line: int | None = None
    new_line: int | None = None

    for line in patch.splitlines():
        header_match = HUNK_HEADER_RE.match(line)
        if header_match:
            old_start = int(header_match.group("old_start"))
            old_lines = int(header_match.group("old_lines") or "1")
            new_start = int(header_match.group("new_start"))
            new_lines = int(header_match.group("new_lines") or "1")
            current = DiffHunk(
                header=line,
                old_start=old_start,
                old_lines=old_lines,
                new_start=new_start,
                new_lines=new_lines,
            )
            hunks.append(current)
            old_line = old_start
            new_line = new_start
            continue

        if current is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current.lines.append(
                DiffLine(type="add", content=line[1:], old_line=None, new_line=new_line)
            )
            if new_line is not None:
                new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.lines.append(
                DiffLine(type="delete", content=line[1:], old_line=old_line, new_line=None)
            )
            if old_line is not None:
                old_line += 1
        elif line.startswith(" "):
            current.lines.append(
                DiffLine(
                    type="context",
                    content=line[1:],
                    old_line=old_line,
                    new_line=new_line,
                )
            )
            if old_line is not None:
                old_line += 1
            if new_line is not None:
                new_line += 1
        elif line.startswith("\\"):
            current.lines.append(DiffLine(type="meta", content=line))

    return hunks
