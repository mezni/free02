"""Unit tests for the parser package and parse-stage dispatch."""

from pathlib import Path

import pytest

from src.ingestion import (
    DiscoveredDocument,
    MarkdownParser,
    ParsedDocument,
    PlainTextParser,
    SourceType,
    parse_document,
    parse_document_structured,
    register_parser,
)
from src.ingestion.parsers import BaseParser


def _discovered(path: str) -> DiscoveredDocument:
    return DiscoveredDocument(
        relative_path=path,
        file_name=path,
        parent_directory=".",
        file_extension=Path(path).suffix.lower(),
        mime_type="text/markdown" if path.endswith(".md") else "text/plain",
        file_hash="hash",
        size_bytes=1,
        modified_at=1.0,
        source=SourceType.FILESYSTEM,
    )


# --- MarkdownParser ---


def test_markdown_parser_extracts_heading_hierarchy(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(
        "# Title\nintro text\n\n## Sub\nsub body\n\n# Title2\nend\n",
        encoding="utf-8",
    )

    sections = MarkdownParser().parse(doc).sections

    assert [s.heading for s in sections] == ["Title", "Sub", "Title2"]
    assert sections[0].level == 1
    assert sections[1].level == 2


def test_markdown_parser_section_content_is_scoped(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(
        "# Title\nintro text\n\n## Sub\nsub body\n\n# Title2\nend\n",
        encoding="utf-8",
    )

    sections = MarkdownParser().parse(doc).sections

    assert "intro text" in sections[0].content
    assert "sub body" in sections[0].content  # nested section stays in parent
    assert "Title2" not in sections[0].content
    assert "# Title" not in sections[0].content  # heading line excluded
    assert sections[2].content == "end"


def test_markdown_parser_handles_no_headings(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("plain paragraph\n\nanother", encoding="utf-8")

    sections = MarkdownParser().parse(doc).sections

    assert len(sections) == 1
    assert sections[0].heading is None
    assert sections[0].level == 0
    assert sections[0].content == "plain paragraph\n\nanother"


def test_markdown_parser_can_parse_extensions():
    assert MarkdownParser().can_parse(Path("a.md"))
    assert MarkdownParser().can_parse(Path("a.markdown"))
    assert not MarkdownParser().can_parse(Path("a.txt"))


def test_plain_text_parser_returns_raw_text(tmp_path):
    doc = tmp_path / "doc.txt"
    doc.write_text("line one\n# not a heading\nline three", encoding="utf-8")

    parsed = PlainTextParser().parse(doc)

    assert parsed.text == "line one\n# not a heading\nline three"
    assert parsed.sections == []


# --- Parse stage dispatch ---


def test_parse_document_selects_parser_by_extension(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    md = raw / "doc.md"
    txt = raw / "notes.txt"
    md.write_text("# Head\nbody", encoding="utf-8")
    txt.write_text("plain", encoding="utf-8")

    assert parse_document(_discovered("doc.md"), raw) == "# Head\nbody"
    assert parse_document(_discovered("notes.txt"), raw) == "plain"


def test_parse_document_structured_returns_markdown_sections(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text("# Head\nbody", encoding="utf-8")

    parsed = parse_document_structured(_discovered("doc.md"), raw)

    assert isinstance(parsed, ParsedDocument)
    assert [s.heading for s in parsed.sections] == ["Head"]


def test_register_parser_takes_priority(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text("content", encoding="utf-8")
    seen: list[str] = []

    class RecordingParser(BaseParser):
        @property
        def supported_extensions(self) -> set[str]:
            return {".md"}

        def parse(self, path: Path) -> ParsedDocument:
            seen.append(str(path))
            return ParsedDocument(text="recording", metadata={})

    try:
        register_parser(RecordingParser())

        assert parse_document(_discovered("doc.md"), raw) == "recording"
        assert seen == [str(raw / "doc.md")]
    finally:
        from src.ingestion.stages import parse as parse_stage

        parse_stage._PARSERS.pop(0)


def test_parse_document_rejects_unregistered_extension(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "notes.xyz").write_text("content", encoding="utf-8")

    discovered = _discovered("notes.xyz")

    with pytest.raises(ValueError, match="No parser registered"):
        parse_document(discovered, raw)
