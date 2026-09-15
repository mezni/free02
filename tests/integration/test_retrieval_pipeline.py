"""Integration tests: retrieval against pgvector chunks seeded via the pipeline stage."""

from src.domain.models.chunk import Chunk
from src.ingestion import ChromaEmbedder, store_chunks
from src.retrieval import Query, RetrievalPipeline, StubLLM


def _chunk(text: str, index: int) -> Chunk:
    return Chunk(
        content=text,
        run_id="run-1",
        doc_id="sop.md:v1",
        index=index,
        doc_metadata={
            "relative_path": "sop.md",
            "version_tag": "v1",
            "tenant_id": "acme",
            "is_active": True,
        },
    )


def _seed(db_session) -> None:
    chunks = [
        _chunk("The late fee is 15 dollars after the grace period.", 0),
        _chunk("Payment is due 20 days from invoice issuance.", 1),
        _chunk("The service is suspended after 45 days past due.", 2),
    ]
    store_chunks(chunks, ChromaEmbedder(), db_session)
    db_session.commit()


def test_answer_returns_retrieved_sources_and_answer(tmp_path, db_session):
    _seed(db_session)

    pipeline = RetrievalPipeline(llm=StubLLM())

    result = pipeline.answer(Query(text="How much is the late fee?", top_k=2))

    assert result.sources
    assert all(source.source == "sop.md" for source in result.sources)
    assert result.answer  # stub returns a deterministic message
    pipeline.close()


def test_build_prompt_includes_top_matching_chunk(tmp_path, db_session):
    _seed(db_session)

    pipeline = RetrievalPipeline(llm=StubLLM())
    result = pipeline.search(Query(text="late fee", top_k=1))

    assert len(result.chunks) == 1
    assert "late fee" in result.chunks[0].text.lower()
    pipeline.close()


def test_search_filters_by_tenant(tmp_path, db_session):
    _seed(db_session)

    pipeline = RetrievalPipeline(llm=StubLLM())
    result = pipeline.search(Query(text="late fee", top_k=5, tenant_id="acme"))

    assert len(result.chunks) > 0
    assert all(source.source == "sop.md" for source in result.chunks)
    pipeline.close()