"""Retrieval data models shared across the pipeline, API, and evaluation."""

from typing import Any

from pydantic import BaseModel, Field


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
    distance: float = Field(default=0.0, description="Vector similarity distance (lower is better)")
    score: float = Field(
        default=0.0, description="Fusion/rerank score (higher is better)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata payload from the chunk row"
    )

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


__all__ = [
    "GenerationResult",
    "Query",
    "RetrievalResult",
    "RetrievedChunk",
]