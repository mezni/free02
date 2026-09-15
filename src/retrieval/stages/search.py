"""Search stage: fetch candidates across transformed queries and strategies."""

from abc import ABC, abstractmethod

from src.retrieval.models import RetrievedChunk
from src.retrieval.strategies.base import SearchStrategy
from src.retrieval.strategies.filters import FilterBundle
from src.retrieval.strategies.hybrid_search import reciprocal_rank_fusion


class SearchStage(ABC):
    """Fetches candidate documents for a set of transformed queries."""

    @abstractmethod
    def search(
        self, queries: list[str], top_k: int, filters: FilterBundle | None
    ) -> list[RetrievedChunk]:
        """Return candidate chunks, best-first, never exceeding ``top_k``."""


class DefaultSearchStage(SearchStage):
    """Run each query against every strategy, merge, and deduplicate."""

    def __init__(self, strategies: list[SearchStrategy]) -> None:
        if not strategies:
            raise ValueError("DefaultSearchStage requires at least one SearchStrategy")
        self._strategies = list(strategies)

    def search(
        self,
        queries: list[str],
        top_k: int,
        filters: FilterBundle | None = None,
    ) -> list[RetrievedChunk]:
        if not queries:
            return []
        merged: list[RetrievedChunk] = []
        for query in queries:
            legs = [
                strategy.search(query, top_k=top_k, filters=filters)
                for strategy in self._strategies
            ]
            ranked = legs[0] if len(legs) == 1 else reciprocal_rank_fusion(legs)
            merged.extend(ranked)
        return _dedupe(merged)[:top_k]


def _dedupe(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[tuple[str, int, str]] = set()
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        key = (chunk.source, chunk.index, chunk.metadata.get("version_tag", ""))
        if key not in seen:
            seen.add(key)
            result.append(chunk)
    return result


__all__ = ["DefaultSearchStage", "SearchStage"]