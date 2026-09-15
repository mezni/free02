"""Shared search-strategy contracts and row-mapping helpers."""

from abc import ABC, abstractmethod

from src.db.models import Chunk
from src.retrieval.models import RetrievedChunk
from src.retrieval.strategies.filters import FilterBundle


class SearchStrategy(ABC):
    """A single-query retrieval operation returning candidates best-first."""

    @abstractmethod
    def search(
        self, query: str, top_k: int, filters: FilterBundle | None
    ) -> list[RetrievedChunk]:
        """Execute one retrieval leg for ``query``."""


def to_retrieved_chunk(
    chunk: Chunk, *, distance: float = 0.0, score: float = 0.0
) -> RetrievedChunk:
    """Map an ORM chunk row into the retrieval result type."""
    return RetrievedChunk(
        text=chunk.content,
        source=chunk.relative_path,
        index=chunk.chunk_index,
        distance=distance,
        score=score,
        metadata=dict(chunk.doc_metadata or {}),
    )


__all__ = ["SearchStrategy", "to_retrieved_chunk"]