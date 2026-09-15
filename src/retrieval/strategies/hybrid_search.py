"""Hybrid search: dense vector + sparse keyword legs merged with Reciprocal Rank Fusion."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Chunk
from src.retrieval.models import RetrievedChunk
from src.retrieval.strategies.base import SearchStrategy, to_retrieved_chunk
from src.retrieval.strategies.filters import FilterBundle
from src.retrieval.strategies.vector_search import VectorSearchStrategy


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]], *, k: int = 60
) -> list[RetrievedChunk]:
    """Merge best-first result lists into a single ranking using RRF.

    Each chunk scores ``sum(1 / (k + rank))`` across the input lists, so
    candidates that rank highly in several strategies float to the top.
    """
    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            key = chunk.id
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in chunks:
                chunks[key] = chunk
    ordered = sorted(chunks.values(), key=lambda c: scores[c.id], reverse=True)
    return [c.model_copy(update={"score": scores[c.id]}) for c in ordered]


class KeywordSearchStrategy(SearchStrategy):
    """Sparse keyword leg backed by Postgres full-text search."""

    def __init__(self, session: Session, *, language: str = "english") -> None:
        self._session = session
        self._language = language

    def search(
        self,
        query: str,
        top_k: int,
        filters: FilterBundle | None = None,
    ) -> list[RetrievedChunk]:
        tsvector = func.to_tsvector(self._language, Chunk.content)
        tsquery = func.plainto_tsquery(self._language, query)
        rank = func.ts_rank(tsvector, tsquery).label("rank")
        predicates = (
            filters.as_predicates() if filters else [Chunk.is_active.is_(True)]
        )
        stmt = (
            select(Chunk, rank)
            .where(Chunk.content.op("@@")(tsquery), *predicates)
            .order_by(rank.desc())
            .limit(top_k)
        )
        rows = self._session.execute(stmt)
        return [
            to_retrieved_chunk(chunk, score=float(score)) for chunk, score in rows
        ]


class HybridSearchStrategy(SearchStrategy):
    """Run the dense vector and sparse keyword legs, then merge with RRF."""

    def __init__(
        self,
        vector: VectorSearchStrategy,
        keyword: KeywordSearchStrategy,
    ) -> None:
        self._vector = vector
        self._keyword = keyword

    def search(
        self,
        query: str,
        top_k: int,
        filters: FilterBundle | None = None,
    ) -> list[RetrievedChunk]:
        legs = [
            self._vector.search(query, top_k=top_k, filters=filters),
            self._keyword.search(query, top_k=top_k, filters=filters),
        ]
        ranked = reciprocal_rank_fusion(legs)
        return ranked[:top_k]


__all__ = [
    "HybridSearchStrategy",
    "KeywordSearchStrategy",
    "reciprocal_rank_fusion",
]