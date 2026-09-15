"""Markdown parser using regex-based extraction (no external dependencies)."""

import re
from pathlib import Path

from src.ingestion.parsers.base import BaseParser, ParsedDocument, Section

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class MarkdownParser(BaseParser):
    """Parse Markdown files into heading-based sections."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".md", ".markdown", ".mdown", ".mkd"}

    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8")
        return ParsedDocument(
            text=text,
            metadata={"source_path": str(path), "parser": "markdown"},
            sections=_extract_sections(text),
        )


def _extract_sections(text: str) -> list[Section]:
    """Split text into level-0 preamble plus heading sections with their content.

    A heading's content spans from just after its own line to the start of the
    next heading at the same-or-higher level. Nested (deeper) headings remain
    part of their ancestor's content.
    """
    matches = list(HEADING_RE.finditer(text))
    sections: list[Section] = []

    if not matches:
        stripped = text.strip()
        if stripped:
            sections.append(Section(heading=None, level=0, content=stripped))
        return sections

    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(Section(heading=None, level=0, content=preamble))

    for index, match in enumerate(matches):
        level = len(match.group(1))
        heading = match.group(2).strip()
        content_start = match.end()
        content_end = next(
            (nxt.start() for nxt in matches[index + 1 :] if len(nxt.group(1)) <= level),
            len(text),
        )
        sections.append(
            Section(
                heading=heading,
                level=level,
                content=text[content_start:content_end].strip(),
            )
        )

    return sections
