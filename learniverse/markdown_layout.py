"""Parse Learniverse structured Markdown notes."""

import hashlib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_NOTES_DIR = Path("data/notes")
LAYOUT_VERSION = "section-author-v1"
AUTHOR_PREFIX = "작성자:"
KEYWORDS_HEADING = "### 키워드"
BODY_HEADING = "### 본문"


# Markdown 입력 계약을 코드로 표현한다.
# 이 parser는 자유로운 Markdown 전체를 해석하지 않고, Learniverse가 약속한
# `# 제목 -> 작성자 -> ## 소제목 -> ### 키워드/### 본문` 구조만 허용한다.
class MarkdownLayoutError(ValueError):
    """Raised when a Markdown note does not match the Learniverse layout."""


# Markdown의 한 `## 소제목` 블록을 코드에서 다루기 위한 데이터 모델이다.
# 이후 DB 저장에서는 이 객체 하나가 `note_sections` row 하나가 된다.
@dataclass(frozen=True)
class StructuredSection:
    heading: str
    keywords: tuple[str, ...]
    body: str


# Markdown 파일 하나를 파싱한 결과다.
# 원문 전체(raw_content)는 `notes`에 저장하고, sections는 관계형 테이블로 나눠 저장한다.
@dataclass(frozen=True)
class StructuredNote:
    title: str
    author: str
    source_path: str
    raw_content: str
    sections: tuple[StructuredSection, ...]


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_structured_notes(notes_dir: str | Path = DEFAULT_NOTES_DIR) -> list[StructuredNote]:
    # 디렉터리 안의 `.md` 파일들을 안정적인 순서로 읽는다.
    # sorted()를 쓰면 운영체제나 파일 시스템에 따라 로딩 순서가 흔들리는 것을 줄일 수 있다.
    directory = Path(notes_dir)
    return [parse_structured_markdown_file(path) for path in sorted(directory.glob("*.md"))]


def parse_structured_markdown_file(path: str | Path) -> StructuredNote:
    note_path = Path(path)
    return parse_structured_markdown(
        note_path.read_text(encoding="utf-8"),
        source_path=str(note_path),
    )


def parse_structured_markdown(content: str, source_path: str) -> StructuredNote:
    # 먼저 문서 전체에서 최상위 `# 제목`을 찾는다.
    # Learniverse 문서 하나는 정확히 하나의 제목만 가져야 DB의 `notes.title`로 안전하게 저장할 수 있다.
    lines = content.splitlines()
    title_positions = [index for index, line in enumerate(lines) if line.startswith("# ")]
    if len(title_positions) != 1:
        raise MarkdownLayoutError(
            f"{source_path}: expected exactly one top-level '# 제목', found {len(title_positions)}."
        )

    title_index = title_positions[0]
    title = lines[title_index][2:].strip()
    if not title:
        raise MarkdownLayoutError(f"{source_path}: top-level title is empty.")

    # 제목 바로 다음 줄은 반드시 `작성자: 이름` 형식이어야 한다.
    # 작성자를 일반 본문처럼 흘려보내지 않고 notes.author에 명확히 저장하기 위한 layout 계약이다.
    author_index = title_index + 1
    if author_index >= len(lines):
        raise MarkdownLayoutError(
            f"{source_path}: expected '{AUTHOR_PREFIX} 이름' immediately after '# 제목'."
        )

    author_line = lines[author_index].strip()
    if not author_line.startswith(AUTHOR_PREFIX):
        raise MarkdownLayoutError(
            f"{source_path}: expected '{AUTHOR_PREFIX} 이름' immediately after '# 제목'."
        )

    author = author_line[len(AUTHOR_PREFIX) :].strip()
    if not author:
        raise MarkdownLayoutError(f"{source_path}: author is empty.")

    # `## 소제목`의 위치를 모두 찾는다.
    # 각 소제목의 시작 위치를 알아야 다음 소제목 전까지를 하나의 section으로 자를 수 있다.
    section_positions = [
        (index, line[3:].strip())
        for index, line in enumerate(lines)
        if line.startswith("## ")
    ]
    if not section_positions:
        raise MarkdownLayoutError(f"{source_path}: expected at least one '## 소제목'.")

    # 작성자 줄과 첫 section 사이에는 설명 문장을 허용하지 않는다.
    # 이렇게 제한하면 문서의 모든 설명 텍스트가 반드시 어떤 section에 속하게 된다.
    first_section_index = section_positions[0][0]
    if any(line.strip() for line in lines[author_index + 1 : first_section_index]):
        raise MarkdownLayoutError(
            f"{source_path}: only blank lines are allowed between author and the first '## 소제목'."
        )

    # section_positions를 기준으로 파일을 여러 section 조각으로 나누고,
    # 각 section 내부가 `### 키워드`와 `### 본문` 규칙을 지키는지 추가로 검증한다.
    sections: list[StructuredSection] = []
    for position, (section_start, heading) in enumerate(section_positions):
        if not heading:
            raise MarkdownLayoutError(f"{source_path}: section heading is empty.")

        section_end = (
            section_positions[position + 1][0]
            if position + 1 < len(section_positions)
            else len(lines)
        )
        sections.append(
            _parse_section(
                source_path=source_path,
                heading=heading,
                lines=lines[section_start + 1 : section_end],
            )
        )

    return StructuredNote(
        title=title,
        author=author,
        source_path=source_path,
        raw_content=content,
        sections=tuple(sections),
    )


def _parse_section(source_path: str, heading: str, lines: list[str]) -> StructuredSection:
    # section 안에서는 `### 키워드`, `### 본문` 두 heading만 허용한다.
    # 예상하지 못한 heading을 조용히 무시하면 DB에 빠진 데이터가 생길 수 있으므로 즉시 실패시킨다.
    for line in lines:
        if line.startswith("### ") and line.strip() not in {KEYWORDS_HEADING, BODY_HEADING}:
            raise MarkdownLayoutError(
                f"{source_path}: section '{heading}' has unsupported heading '{line.strip()}'."
            )

    # 하나의 section에는 키워드 블록과 본문 블록이 각각 정확히 하나씩 있어야 한다.
    # 이 규칙 덕분에 나중에 keyword는 `section_keywords`, body는 `note_sections.body`로 명확히 나뉜다.
    keyword_positions = [
        index for index, line in enumerate(lines) if line.strip() == KEYWORDS_HEADING
    ]
    body_positions = [index for index, line in enumerate(lines) if line.strip() == BODY_HEADING]

    if len(keyword_positions) != 1:
        raise MarkdownLayoutError(
            f"{source_path}: section '{heading}' must have exactly one '{KEYWORDS_HEADING}' block."
        )
    if len(body_positions) != 1:
        raise MarkdownLayoutError(
            f"{source_path}: section '{heading}' must have exactly one '{BODY_HEADING}' block."
        )

    keyword_index = keyword_positions[0]
    body_index = body_positions[0]
    # 키워드가 본문보다 먼저 와야 한다는 순서도 layout 계약의 일부다.
    # 순서를 고정하면 parser가 단순해지고, 사람이 문서를 읽을 때도 예측 가능해진다.
    if body_index < keyword_index:
        raise MarkdownLayoutError(
            f"{source_path}: section '{heading}' must place '{KEYWORDS_HEADING}' before '{BODY_HEADING}'."
        )
    if any(line.strip() for line in lines[:keyword_index]):
        raise MarkdownLayoutError(
            f"{source_path}: section '{heading}' has content before '{KEYWORDS_HEADING}'."
        )

    # 키워드 영역은 bullet list로 파싱하고, 본문 영역은 여러 줄을 하나의 설명 문자열로 합친다.
    # 두 값을 분리해 두면 embedding 입력을 만들 때 제목/키워드/본문을 원하는 방식으로 조합할 수 있다.
    keywords = _parse_keywords(
        source_path=source_path,
        heading=heading,
        lines=lines[keyword_index + 1 : body_index],
    )
    body = "\n".join(lines[body_index + 1 :]).strip()
    if not body:
        raise MarkdownLayoutError(f"{source_path}: section '{heading}' body is empty.")

    return StructuredSection(heading=heading, keywords=keywords, body=body)


def _parse_keywords(source_path: str, heading: str, lines: list[str]) -> tuple[str, ...]:
    # 빈 줄은 layout을 읽기 좋게 만들기 위한 장식이므로 제거하고,
    # 실제 내용이 있는 줄만 keyword 후보로 본다.
    keyword_lines = [line.strip() for line in lines if line.strip()]
    if not keyword_lines:
        raise MarkdownLayoutError(f"{source_path}: section '{heading}' has no keywords.")

    keywords: list[str] = []
    for line in keyword_lines:
        # 키워드는 반드시 `- keyword` 형태여야 한다.
        # 번호 목록이나 일반 문장을 허용하지 않으면 DB에 저장되는 keyword 형식이 일정해진다.
        if not line.startswith("- "):
            raise MarkdownLayoutError(
                f"{source_path}: section '{heading}' keyword must be a '- keyword' bullet."
            )
        keyword = line[2:].strip()
        if not keyword:
            raise MarkdownLayoutError(f"{source_path}: section '{heading}' has an empty keyword.")
        keywords.append(keyword)

    return tuple(keywords)
