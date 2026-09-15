"""Parse stage: pluggable document parsers."""

from pathlib import Path

from src.domain.models.document import DiscoveredDocument
from src.ingestion.parsers import (
    BaseParser,
    MarkdownParser,
    ParsedDocument,
    PlainTextParser,
)

_PARSERS: list[BaseParser] = [MarkdownParser(), PlainTextParser()]


def register_parser(parser: BaseParser) -> None:
    """Register a new parser (inserted at front for priority)."""
    _PARSERS.insert(0, parser)


def _get_parser(path: Path) -> BaseParser:
    for parser in _PARSERS:
        if parser.can_parse(path):
            return parser
    raise ValueError(
        f"No parser registered for file extension {path.suffix!r} "
        f"(registered: {sorted({ext for p in _PARSERS for ext in p.supported_extensions})})"
    )


def load_raw_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_document(discovered: DiscoveredDocument, raw_dir: Path) -> str:
    """Load and parse a document, returning plain text for backward compatibility."""
    file_path = raw_dir / discovered.relative_path
    return _get_parser(file_path).parse(file_path).text


def parse_document_structured(
    discovered: DiscoveredDocument, raw_dir: Path
) -> ParsedDocument:
    """Load and parse a document, returning the full structured result."""
    file_path = raw_dir / discovered.relative_path
    return _get_parser(file_path).parse(file_path)
