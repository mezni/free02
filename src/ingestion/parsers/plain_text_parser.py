"""Plain-text parser: no structural extraction, raw text only."""

from pathlib import Path

from src.ingestion.parsers.base import BaseParser, ParsedDocument


class PlainTextParser(BaseParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".txt", ".text"}

    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8")
        return ParsedDocument(
            text=text,
            metadata={"source_path": str(path), "parser": "plain-text"},
        )
