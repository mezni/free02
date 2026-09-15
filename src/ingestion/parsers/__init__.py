"""Parser package: pluggable document parsers."""

from src.ingestion.parsers.base import BaseParser, ParsedDocument, Section
from src.ingestion.parsers.markdown_parser import MarkdownParser
from src.ingestion.parsers.plain_text_parser import PlainTextParser

__all__ = [
    "BaseParser",
    "MarkdownParser",
    "ParsedDocument",
    "PlainTextParser",
    "Section",
]
