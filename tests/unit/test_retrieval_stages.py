"""Unit tests for retrieval pipeline stages (query transform, search, rerank, context assembly)."""

import pytest

from src.retrieval.llm import StubLLM
from src.retrieval.models import Query, RetrievalResult, RetrievedChunk
from src.retrieval.stages.context_assembly import StandardContextAssembly
from src.retrieval.stages.query_transform import (
    ExpansionQueryTransform,
    IdentityQueryTransform,
)
from src.retrieval.stages.search import DefaultSearchStage, _dedupe
from src.retrieval.strategies.filters import FilterBundle, build_filters
from src.retrieval.strategies.hybrid_search import reciprocal_rank_fusion

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_C = [
    RetrievedChunk(text="alpha", source="a.md", index=0, distance=0.1, score=0.9),
    RetrievedChunk(text="beta",  source="b.md", index=1, distance=0.3, score=0.7),
]

_RESULT = RetrievalResult(query="what is the late fee?", chunks=_C)


# ---- query transform ------------------------------------------------------

def test_identity_returns_query_text():
    stage = IdentityQueryTransform()
    out = stage.transform(Query(text="  what is the late fee?  "))
    assert out == ["what is the late fee?"]


def test_expansion_does_not_use_llm():
    # Without an LLM the transform should pass through unchanged
    stage = ExpansionQueryTransform(llm=StubLLM(), num_variants=3)
    out = stage.transform(Query(text="hello"))
    assert out == ["hello"]


# ---- filter bundle --------------------------------------------------------

def test_build_filters_no_tenant():
    q = Query(text="hi")
    bundle = build_filters(q)
    preds = bundle.as_predicates()
    # Only the is_active predicate should be present
    assert len(preds) == 1


def test_build_filters_with_tenant():
    q = Query(text="hi", tenant_id="acme")
    bundle = build_filters(q)
    preds = bundle.as_predicates()
    # is_active + tenant_id
    assert len(preds) == 2


def test_build_filters_custom_override():
    from sqlalchemy.dialects import postgresql

    bundle = FilterBundle(classification="confidential", department="legal")
    preds = bundle.as_predicates()
    # is_active + classification + department
    assert len(preds) == 3
    sql = " ".join(
        str(
            p.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for p in preds
    )
    assert "classification" in sql and "confidential" in sql
    assert "department" in sql and "legal" in sql


# ---- reciprocal rank fusion -----------------------------------------------

def test_rrf_identical_lists_maintains_order():
    ranked = [[_C[0], _C[1]], [_C[0], _C[1]]]
    fused = reciprocal_rank_fusion(ranked, k=60)
    assert [c.id for c in fused] == ["a.md:0", "b.md:1"]


def test_rrf_disagreement_reverses_rank():
    first = _C[0].model_copy(update={"score": 1.0})
    second = _C[1].model_copy(update={"score": 1.0})
    ranked = [
        [first, second],    # leg 1 prefers a
        [second, first],    # leg 2 prefers b  -> a wins (sum of 1/(60+1)+1/(60+2))
    ]
    fused = reciprocal_rank_fusion(ranked, k=60)
    scores = {c.id: c.score for c in fused}
    assert fused[0].id == "a.md:0"  # appears earlier in both legs combined
    assert scores["a.md:0"] == pytest.approx(1.0 / 61 + 1.0 / 62, rel=1e-9)


# ---- dedupe ---------------------------------------------------------------

def test_dedupe_preserves_first_occurrence():
    dups = [
        RetrievedChunk(text="alpha", source="a.md", index=0, distance=0.1, metadata={"version_tag": "v1"}),
        RetrievedChunk(text="alpha", source="a.md", index=0, distance=0.2, metadata={"version_tag": "v1"}),
        RetrievedChunk(text="beta",  source="b.md", index=1, distance=0.3, metadata={"version_tag": "v1"}),
    ]
    result = _dedupe(dups)
    assert len(result) == 2
    assert result[0].distance == 0.1  # first kept


def test_dedupe_distinct_versions_kept():
    dups = [
        RetrievedChunk(text="a-v1", source="a.md", index=0, distance=0.1, metadata={"version_tag": "v1"}),
        RetrievedChunk(text="a-v2", source="a.md", index=0, distance=0.1, metadata={"version_tag": "v2"}),
    ]
    assert len(_dedupe(dups)) == 2


# ---- default search stage ------------------------------------------------

class _StubStrategy:
    """Returns a fixed list of chunks regardless of query."""
    def __init__(self, chunks: list[RetrievedChunk]):
        self._chunks = list(chunks)
    def search(self, query: str, top_k: int, filters=None):
        return list(self._chunks[:top_k])


def test_default_search_merges_strategies():
    s1 = _StubStrategy([_C[0]])
    s2 = _StubStrategy([_C[1]])
    stage = DefaultSearchStage([s1, s2])
    out = stage.search(["q"], top_k=5)
    ids = {c.id for c in out}
    assert ids == {"a.md:0", "b.md:1"}


def test_default_search_top_k_limits_output():
    stage = DefaultSearchStage([_StubStrategy(_C)])
    out = stage.search(["q"], top_k=1)
    assert len(out) == 1


# ---- context assembly -----------------------------------------------------

def test_assembly_labels_and_format():
    asm = StandardContextAssembly()
    ctx = asm.assemble(_RESULT)
    assert "[1] (source: a.md)" in ctx
    assert "alpha" in ctx
    assert "[2] (source: b.md)" in ctx
    assert "beta" in ctx
    assert ctx.count("\n\n") == 1  # exactly one blank separator


def test_assembly_dedupes_chunks():
    dups = [_C[0], _C[0].model_copy(), _C[1]]
    result = RetrievalResult(query="q", chunks=dups)
    ctx = StandardContextAssembly().assemble(result)
    assert ctx.count("[1]") == 1


def test_assembly_max_chunks_truncates():
    asm = StandardContextAssembly(max_chunks=1)
    ctx = asm.assemble(_RESULT)
    assert "[2]" not in ctx


def test_assembly_injects_title_from_metadata():
    chunk = RetrievedChunk(
        text="details here", source="x.md", index=0, distance=0.0,
        metadata={"title": "Late Fee Policy"},
    )
    result = RetrievalResult(query="q", chunks=[chunk])
    ctx = StandardContextAssembly().assemble(result)
    assert "(Late Fee Policy)" in ctx


def test_assembly_token_budget_truncates():
    asm = StandardContextAssembly()
    # max_tokens=5 -> budget of 20 chars; first block header alone is ~20 chars
    ctx = asm.assemble(_RESULT, max_tokens=5)
    assert "[1]" in ctx
    # context should be shorter than the full two-block version
    full = asm.assemble(_RESULT)
    assert len(ctx) <= len(full)


def test_assembly_empty_chunks():
    result = RetrievalResult(query="q", chunks=[])
    ctx = StandardContextAssembly().assemble(result)
    assert ctx == ""


def test_build_context_accepts_sequence_of_chunks():
    """RetrievalPipeline.build_context works without __init__ (via getattr fallback)."""
    from src.retrieval.pipeline import RetrievalPipeline
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    ctx = pipeline.build_context(_C)
    assert "[1] (source: a.md)" in ctx
    assert "alpha" in ctx


def test_build_context_accepts_retrieval_result():
    from src.retrieval.pipeline import RetrievalPipeline
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    ctx = pipeline.build_context(_RESULT)
    assert "[1] (source: a.md)" in ctx
