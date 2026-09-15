"""Markdown parser using LlamaIndex's MarkdownNodeParser for heading-based sections."""

import re
from pathlib import Path

from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document

from src.ingestion.parsers._loaders import load_document
from src.ingestion.parsers.base import BaseParser, ParsedDocument, Section

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


class MarkdownParser(BaseParser):
    """Parse Markdown files into heading-based sections.

    Text is loaded via LlamaIndex's SimpleDirectoryReader; the section structure
    is produced by LlamaIndex's MarkdownNodeParser (heading-aware splitting that
    ignores headings inside fenced code blocks).
    """

    @property
    def supported_extensions(self) -> set[str]:
        return {".md", ".markdown", ".mdown", ".mkd"}

    def parse(self, path: Path) -> ParsedDocument:
        text, metadata = load_document(path)
        document = Document(text=text, metadata=metadata)
        nodes = MarkdownNodeParser().get_nodes_from_documents([document])
        return ParsedDocument(
            text=text,
            metadata={"source_path": str(path), "parser": "markdown", **metadata},
            sections=_extract_sections(nodes),
        )


def _node_entry(node) -> dict:
    """Extract (heading, level, own content) from a LlamaIndex markdown node."""
    text = node.text.strip()
    lines = text.splitlines()
    first_line = lines[0].strip() if lines else ""
    match = HEADING_RE.match(first_line)
    if match:
        return {
            "heading": match.group(2).strip(),
            "level": len(match.group(1)),
            "content": "\n".join(lines[1:]).strip(),
        }
    return {"heading": None, "level": 0, "content": text}


def _extract_sections(nodes: list) -> list[Section]:
    """Reconstruct hierarchical Section objects from LlamaIndex nodes.

    A heading's content spans its own text plus the content of every descendant
    section (nested headings stay within their ancestor), excluding heading lines
    and preamble text preceding the first heading.
    """
    roots: list[dict] = []
    all_holders: list[dict] = []
    stack: list[dict] = []

    for node in nodes:
        entry = _node_entry(node)
        section = Section(
            heading=entry["heading"], level=entry["level"], content=entry["content"]
        )
        holder = {"section": section, "pending": []}
        all_holders.append(holder)
        while stack and stack[-1]["level"] >= entry["level"]:
            stack.pop()
        if stack:
            stack[-1]["pending"].append(holder)
        else:
            roots.append(holder)
        if entry["heading"] is not None:
            stack.append({"level": entry["level"], "pending": holder["pending"]})

    def fold(section: Section, pending: list[dict]) -> str:
        parts = [
            section.content,
            *(fold(holder["section"], holder["pending"]) for holder in pending),
        ]
        return "\n\n".join(part for part in parts)

    for holder in all_holders:
        holder["section"].content = fold(holder["section"], holder["pending"])

    return [holder["section"] for holder in all_holders]