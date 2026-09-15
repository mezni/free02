"""Rerank stage: refine and reorder candidate results after search."""

import re
from abc import ABC, abstractmethod

from src.config import settings
from src.retrieval.llm import LLM, OpenAICompatibleLLM
from src.retrieval.models import RetrievalResult


class RerankStage(ABC):
    """Scores and re-orders candidates, optionally pruning weak matches."""

    @abstractmethod
    def rerank(self, result: RetrievalResult) -> RetrievalResult:
        """Return a result whose chunks are high-quality and best-first."""


class IdentityReranker(RerankStage):
    """Keep the strategy ordering unchanged (default, zero cost)."""

    def rerank(self, result: RetrievalResult) -> RetrievalResult:
        return result


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class LLMReranker(RerankStage):
    """Coarse LLM-as-judge rerank: score each candidate 0-10 on relevance."""

    PROMPT = (
        "Rate how relevant the following chunk is to the user question, on a scale "
        "of 0 (completely unrelated) to 10 (exact answer). Respond with only one "
        "integer.\nQuestion: {question}\nChunk: {chunk}"
    )

    def __init__(
        self,
        llm: LLM | None = None,
        *,
        min_score: float = 5.0,
        top_k: int | None = None,
        max_chunk_chars: int = 1500,
    ) -> None:
        self._llm = llm or (OpenAICompatibleLLM() if settings.llm_api_key else None)
        self._min_score = min_score
        self._top_k = top_k
        self._max_chunk_chars = max_chunk_chars

    def rerank(self, result: RetrievalResult) -> RetrievalResult:
        if not isinstance(self._llm, OpenAICompatibleLLM) or not result.chunks:
            return result
        scored: list = []
        for chunk in result.chunks:
            prompt = self.PROMPT.format(
                question=result.query, chunk=chunk.text[: self._max_chunk_chars]
            )
            match = _NUMBER.search(self._llm.complete(prompt))
            score = float(match.group(0)) if match else 0.0
            scored.append(chunk.model_copy(update={"score": score}))
        scored.sort(key=lambda c: c.score, reverse=True)
        if self._min_score is not None:
            scored = [c for c in scored if c.score >= self._min_score]
        if self._top_k is not None:
            scored = scored[: self._top_k]
        return RetrievalResult(query=result.query, chunks=scored)


class CrossEncoderReranker(RerankStage):
    """Cross-encoder rerank (Cohere / BGE style) via ``sentence-transformers``.

    Degrades gracefully to the original ordering when the optional dependency is
    not installed, so the pipeline keeps working without a cross-encoder.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base", *, keep_top_k: int | None = None) -> None:
        self._model_name = model_name
        self._keep_top_k = keep_top_k
        self._encoder: object | None = None

    def _load(self):
        if self._encoder is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError:
                self._encoder = False
            else:
                self._encoder = CrossEncoder(self._model_name)
        return self._encoder

    def rerank(self, result: RetrievalResult) -> RetrievalResult:
        encoder = self._load()
        if not encoder or not result.chunks:
            return result
        pairs = [(result.query, chunk.text) for chunk in result.chunks]
        scores = encoder.predict(pairs, show_progress_bar=False)
        for chunk, score in zip(result.chunks, scores, strict=True):
            chunk.score = float(score)
        ordered = sorted(result.chunks, key=lambda c: c.score, reverse=True)
        if self._keep_top_k is not None:
            ordered = ordered[: self._keep_top_k]
        return RetrievalResult(query=result.query, chunks=ordered)


__all__ = ["CrossEncoderReranker", "IdentityReranker", "LLMReranker", "RerankStage"]