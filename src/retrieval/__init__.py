"""Retrieval package: staged pipeline for querying the pgvector knowledge base."""

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
from src.retrieval.stages import (
    ContextAssemblyStage,
    CrossEncoderReranker,
    DefaultSearchStage,
    ExpansionQueryTransform,
    HyDEQueryTransform,
    IdentityQueryTransform,
    IdentityReranker,
    LLMReranker,
    QueryTransformStage,
    RerankStage,
    SearchStage,
    StandardContextAssembly,
)
from src.retrieval.strategies import (
    FilterBundle,
    HybridSearchStrategy,
    KeywordSearchStrategy,
    SearchStrategy,
    VectorSearchStrategy,
    build_filters,
    reciprocal_rank_fusion,
    to_retrieved_chunk,
)

__all__ = [
    "LLM",
    "SYSTEM_PROMPT",
    "ContextAssemblyStage",
    "CrossEncoderReranker",
    "DefaultSearchStage",
    "ExpansionQueryTransform",
    "FilterBundle",
    "GenerationResult",
    "HyDEQueryTransform",
    "HybridSearchStrategy",
    "IdentityQueryTransform",
    "IdentityReranker",
    "KeywordSearchStrategy",
    "LLMReranker",
    "OpenAICompatibleLLM",
    "Query",
    "QueryTransformStage",
    "RerankStage",
    "RetrievalPipeline",
    "RetrievalResult",
    "RetrievedChunk",
    "SearchStage",
    "SearchStrategy",
    "StandardContextAssembly",
    "StubLLM",
    "VectorSearchStrategy",
    "build_filters",
    "reciprocal_rank_fusion",
    "to_retrieved_chunk",
]