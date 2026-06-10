#!/usr/bin/env python3
"""PR 하나를 가져오는 MVP 실행 파일."""

from __future__ import annotations

import sys
from pathlib import Path


# 파일 경로로 직접 실행해도 패키지 import가 되도록 프로젝트 루트를 추가한다.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pr_atlas_mvp.runner import main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("\n중단되었습니다.")
