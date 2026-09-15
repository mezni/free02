"""Chunk model: content, provenance identifiers, and vector metadata payload."""

from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """Chunk model containing content text and injected document metadata dictionary."""

    content: str
    run_id: str
    doc_id: str
    index: int
    doc_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        version_tag = self.doc_metadata.get("version_tag", "v1")
        source_file = self.doc_metadata.get("relative_path", "file")
        return f"{source_file}:{version_tag}:{self.index}"

    def get_vector_metadata(self) -> dict[str, Any]:
        """Build Chroma-compatible metadata combining chunk index and document metadata."""
        return {
            **self.doc_metadata,
            "run_id": self.run_id,
            "chunk_index": self.index,
        }
