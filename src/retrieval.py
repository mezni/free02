"""Retrieval: embed query → pgvector search → context assembly → LLM generation."""

from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import settings
from src.db.repositories import EmbeddingRepository
from src.db.session import SessionLocal
from src.ingestion import ChromaEmbedder, Embedder

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question using only the provided "
    "context. If the context does not contain the answer, say so. Cite the "
    "source file for each claim."
)


class Query(BaseModel):
    text: str = Field(min_length=1, description="Question to answer")
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of chunks to retrieve"
    )
    tenant_id: str | None = Field(
        default=None, description="Restrict retrieval to this tenant"
    )


class RetrievedChunk(BaseModel):
    text: str
    source: str
    index: int
    distance: float

    @property
    def id(self) -> str:
        return f"{self.source}:{self.index}"


class RetrievalResult(BaseModel):
    query: str
    chunks: list[RetrievedChunk]


class GenerationResult(BaseModel):
    answer: str
    sources: list[RetrievedChunk]
    model: str


class LLM(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return a completion for `prompt`."""


class OpenAICompatibleLLM(LLM):
    """Chat-completions client for OpenAI and compatible endpoints."""

    def __init__(
        self,
        api_key: str = settings.llm_api_key,
        model: str = settings.llm_model,
        base_url: str = settings.llm_base_url,
        timeout: float = settings.llm_timeout,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete(self, prompt: str) -> str:
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._client.close()


class StubLLM(LLM):
    """Deterministic fallback used when no LLM API key is configured."""

    def complete(self, prompt: str) -> str:
        return "[stub] No LLM configured (set LLM_API_KEY); returning retrieved context only."


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
        return GenerationResult(answer=answer, sources=result.chunks, model=self.model)


if __name__ == "__main__":
    pipeline = RetrievalPipeline()
    try:
        generation = pipeline.answer(
            Query(text="What is the late fee for delinquent accounts?")
        )
        print(generation.answer)
        for source in generation.sources:
            print(f"- {source.source} (distance {source.distance:.4f})")
    finally:
        pipeline.close()
