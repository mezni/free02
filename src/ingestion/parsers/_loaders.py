"""LlamaIndex-backed file loading shared by the parsers."""

from pathlib import Path
from typing import Any

from llama_index.core.readers.file.base import SimpleDirectoryReader


def load_document(path: Path) -> tuple[str, dict[str, Any]]:
    """Load a file's text and metadata through LlamaIndex's SimpleDirectoryReader.

    Returns (text, metadata), falling back to a plain read if the reader produced
    no document (e.g. an empty file).
    """
    documents = SimpleDirectoryReader(input_files=[str(path)]).load_data()
    if not documents or not documents[0].text:
        return path.read_text(encoding="utf-8"), {"file_path": str(path)}
    return documents[0].text, dict(documents[0].metadata)