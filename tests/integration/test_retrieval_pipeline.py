"""Integration tests: retrieval against a real seeded ChromaDB store."""

import chromadb

from src.ingestion import ChromaEmbedder, Chunk, store
from src.retrieval import Query, RetrievalPipeline, StubLLM


def _seed(persist) -> None:
    client = chromadb.PersistentClient(path=str(persist))
    chunks = [
        Chunk(
            text="The late fee is 15 dollars after the grace period.",
            source="sop.md",
            index=0,
        ),
        Chunk(
            text="Payment is due 20 days from invoice issuance.",
            source="sop.md",
            index=1,
        ),
        Chunk(
            text="The service is suspended after 45 days past due.",
            source="sop.md",
            index=2,
        ),
    ]
    store(chunks, ChromaEmbedder(), client)
    client.close()


def test_answer_returns_retrieved_sources_and_answer(tmp_path):
    persist = tmp_path / "chroma"
    _seed(persist)

    pipeline = RetrievalPipeline(llm=StubLLM(), persist_dir=persist)

    result = pipeline.answer(Query(text="How much is the late fee?", top_k=2))

    assert result.sources
    assert all(source.source == "sop.md" for source in result.sources)
    assert result.answer  # stub returns a deterministic message
    pipeline.close()


def test_build_prompt_includes_top_matching_chunk(tmp_path):
    persist = tmp_path / "chroma"
    _seed(persist)

    pipeline = RetrievalPipeline(llm=StubLLM(), persist_dir=persist)
    result = pipeline.search(Query(text="late fee", top_k=1))

    assert len(result.chunks) == 1
    assert "late fee" in result.chunks[0].text.lower()
    pipeline.close()

    # Chroma keeps the file handle open until the process exits.
    chromadb.PersistentClient(path=str(persist)).close()
