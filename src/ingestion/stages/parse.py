"""Parse stage: load raw text from discovered files."""

from pathlib import Path

from src.domain.models.document import DiscoveredDocument


def load_raw_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_document(discovered: DiscoveredDocument, raw_dir: Path) -> str:
    """Load the raw file content for a discovered document."""
    file_path = raw_dir / discovered.relative_path
    return load_raw_text(file_path)
