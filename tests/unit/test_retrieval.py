"""Unit tests for src/retrieval schemas and context assembly."""

import pytest
from pydantic import ValidationError

from src.retrieval import (
    Query,
    RetrievalPipeline,
    RetrievalResult,
    RetrievedChunk,
    StubLLM,
)

_CHUNKS = [
    RetrievedChunk(text="alpha", source="a.md", index=0, distance=0.1),
    RetrievedChunk(text="beta", source="b.md", index=2, distance=0.8),
]


def test_query_validates_text_and_top_k():
    with pytest.raises(ValidationError):
        Query(text="", top_k=5)
    with pytest.raises(ValidationError):
        Query(text="hi", top_k=0)
    with pytest.raises(ValidationError):
        Query(text="hi", top_k=21)

    assert Query(text="hello", top_k=3).top_k == 3


def test_retrieved_chunk_id():
    assert (
        RetrievedChunk(text="x", source="doc.md", index=7, distance=0.5).id
        == "doc.md:7"
    )


def test_build_context_labels_sources():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    result = RetrievalResult(query="q", chunks=_CHUNKS)

    context = pipeline.build_context(result)

    assert "[1] (source: a.md)" in context and "alpha" in context
    assert "[2] (source: b.md)" in context and "beta" in context


def test_build_prompt_contains_context_and_question():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    result = RetrievalResult(query="what is the late fee?", chunks=_CHUNKS)

    prompt = pipeline.build_prompt(result)

    assert "Context:" in prompt
    assert "what is the late fee?" in prompt
    assert "Answer:" in prompt


def test_stub_llm_returns_deterministic_answer():
    assert "No LLM configured" in StubLLM().complete("anything")
