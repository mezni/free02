"""Retrieval pipeline: embed query → pgvector search → context assembly → LLM generation."""

from sqlalchemy.orm import Session

from src.config import settings
from src.db.repositories import EmbeddingRepository
from src.db.session import SessionLocal
from src.ingestion import ChromaEmbedder, Embedder
from src.retrieval.llm import LLM, OpenAICompatibleLLM, StubLLM
from src.retrieval.models import (
    GenerationResult,
    Query,
    RetrievalResult,
    RetrievedChunk,
)


class RetrievalPipeline:
    def __init__(
        self,
        embedder: Embedder | None = None,
        llm: LLM | None = None,
        db_session: Session | None = None,
    ) -> None:
        self._embedder = embedder or ChromaEmbedder()
        self._llm = llm or (
            OpenAICompatibleLLM() if settings.llm_api_key else StubLLM()
        )
        self.model = getattr(self._llm, "model", "stub")
        self._owns_session = db_session is None
        self._session = db_session or SessionLocal()

    def close(self) -> None:
        if isinstance(self._llm, OpenAICompatibleLLM):
            self._llm.close()
        if self._owns_session:
            self._session.close()

    def embed_query(self, query: Query) -> list[float]:
        """Step 1: normalize and embed the query."""
        embedded = self._embedder.embed_texts([query.text.strip()])
        return embedded[0]

    def search(self, query: Query) -> RetrievalResult:
        """Step 2: nearest-neighbour search against the pgvector index."""
        query_vector = self.embed_query(query)
        rows = EmbeddingRepository(self._session).search(
            query_vector, top_k=query.top_k, tenant_id=query.tenant_id
        )
        chunks = [
            RetrievedChunk(
                text=chunk.content,
                source=chunk.relative_path,
                index=chunk.chunk_index,
                distance=score,
            )
            for chunk, score in rows
        ]
        return RetrievalResult(query=query.text, chunks=chunks)

    def build_context(self, result: RetrievalResult) -> str:
        """Step 3a: assemble retrieved chunks into labelled context blocks."""
        blocks = [
            f"[{i + 1}] (source: {chunk.source})\n{chunk.text}"
            for i, chunk in enumerate(result.chunks)
        ]
        return "\n\n".join(blocks)

    def build_prompt(self, result: RetrievalResult) -> str:
        """Step 3b: format the final prompt for the LLM."""
        return (
            f"Context:\n{self.build_context(result)}\n\n"
            f"Question: {result.query}\nAnswer:"
        )

    def generate(self, prompt: str) -> str:
        """Step 4: generate the answer."""
        return self._llm.complete(prompt)

    def answer(self, query: Query) -> GenerationResult:
        """Run the full retrieval + generation pipeline."""
        result = self.search(query)
        prompt = self.build_prompt(result)
        answer = self.generate(prompt)
        return GenerationResult(
            answer=answer, sources=result.chunks, model=self.model
        )


__all__ = ["RetrievalPipeline"]