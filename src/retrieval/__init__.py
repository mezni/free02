"""Retrieval package: query/LLM interfaces and the pgvector retrieval pipeline."""

from src.retrieval.llm import (
    LLM,
    SYSTEM_PROMPT,
    OpenAICompatibleLLM,
    StubLLM,
)
from src.retrieval.models import (
    GenerationResult,
    Query,
    RetrievalResult,
    RetrievedChunk,
)
from src.retrieval.pipeline import RetrievalPipeline

__all__ = [
    "LLM",
    "SYSTEM_PROMPT",
    "GenerationResult",
    "OpenAICompatibleLLM",
    "Query",
    "RetrievalPipeline",
    "RetrievalResult",
    "RetrievedChunk",
    "StubLLM",
]