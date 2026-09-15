"""Chunk stage: split normalized text into chunks bound to a document/run."""

from src.domain.models.chunk import Chunk


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph
    if current:
        chunks.append(current)
    return chunks


def build_chunks(
    text: str,
    doc_id: str,
    run_id: str,
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    """Turn cleaned text into Chunk objects without document-enrichment metadata."""
    return [
        Chunk(content=part, run_id=run_id, doc_id=doc_id, index=index)
        for index, part in enumerate(chunk_text(text, chunk_size, overlap))
    ]
