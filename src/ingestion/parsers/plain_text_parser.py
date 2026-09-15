"""Plain-text parser backed by LlamaIndex: raw text, no structural extraction."""

from pathlib import Path

from src.ingestion.parsers._loaders import load_document
from src.ingestion.parsers.base import BaseParser, ParsedDocument


class PlainTextParser(BaseParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".txt", ".text"}

    def parse(self, path: Path) -> ParsedDocument:
        text, metadata = load_document(path)
        return ParsedDocument(
            text=text,
            metadata={"source_path": str(path), "parser": "plain-text", **metadata},
        )