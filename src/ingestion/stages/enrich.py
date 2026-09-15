"""Enrich stage: inject full document metadata into every chunk."""

from src.domain.models.chunk import Chunk
from src.domain.models.document import DocumentRecord


def enrich_chunks(chunks: list[Chunk], doc_record: DocumentRecord) -> list[Chunk]:
    """Attach the flattened document metadata dict to each chunk."""
    injected_metadata = doc_record.to_dict()
    return [
        chunk.model_copy(update={"doc_metadata": injected_metadata}) for chunk in chunks
    ]
