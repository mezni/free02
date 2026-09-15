"""Dense vector search strategy over pgvector."""

from src.db.repositories import EmbeddingRepository
from src.ingestion import Embedder
from src.retrieval.models import RetrievedChunk
from src.retrieval.strategies.base import SearchStrategy, to_retrieved_chunk
from src.retrieval.strategies.filters import FilterBundle


class VectorSearchStrategy(SearchStrategy):
    """Embed the query and run a cosine nearest-neighbour search."""

    def __init__(self, embedder: Embedder, session) -> None:
        self._embedder = embedder
        self._repository = EmbeddingRepository(session)

    def search(
        self,
        query: str,
        top_k: int,
        filters: FilterBundle | None = None,
    ) -> list[RetrievedChunk]:
        vector = self._embedder.embed_texts([query.strip()])[0]
        predicates = filters.as_predicates() if filters else None
        rows = self._repository.search(vector, top_k=top_k, filters=predicates)
        return [to_retrieved_chunk(chunk, distance=distance) for chunk, distance in rows]


__all__ = ["VectorSearchStrategy"]