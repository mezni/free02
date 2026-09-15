"""Integration tests: end-to-end pipeline into a real ChromaDB store."""

import chromadb

from src.ingestion import (
    ChromaEmbedder,
    Chunk,
    PipelineConfig,
    run_pipeline,
    store_chunks,
)


def test_run_pipeline_ingests_markdown(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text(
        ("word " * 200) + "\n\n" + ("zebra " * 200), encoding="utf-8"
    )
    persist = tmp_path / "chroma"
    config = PipelineConfig(raw_dir=raw, persist_dir=persist)

    run, chunks = run_pipeline(config)

    assert len(chunks) > 1
    assert persist.exists()
    assert run.chunks_created == len(chunks)

    collection = _collection(persist)
    assert collection.count() == len(chunks)
    sources = {
        meta["relative_path"]
        for meta in collection.get(include=["metadatas"])["metadatas"]
    }
    assert sources == {"doc.md"}


def test_run_pipeline_recreate_wipes_previous_data(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    persist = tmp_path / "chroma"
    config = PipelineConfig(raw_dir=raw, persist_dir=persist)

    (raw / "a.md").write_text("hello", encoding="utf-8")
    run_pipeline(config)
    (raw / "a.md").unlink()
    (raw / "b.md").write_text("world", encoding="utf-8")
    run_pipeline(PipelineConfig(raw_dir=raw, persist_dir=persist, recreate=True))

    collection = _collection(persist)
    assert collection.count() == 1
    assert {
        meta["relative_path"]
        for meta in collection.get(include=["metadatas"])["metadatas"]
    } == {"b.md"}


def test_chromadb_store_chunks_upserts(tmp_path):
    persist = tmp_path / "chroma"
    client = chromadb.PersistentClient(path=str(persist))

    def chunk(text: str, index: int) -> Chunk:
        return Chunk(
            content=text,
            run_id="run-1",
            doc_id="doc.md:v1",
            index=index,
            doc_metadata={
                "relative_path": "doc.md",
                "version_tag": "v1",
                "is_active": True,
            },
        )

    first = [chunk("alpha", 0)]
    second = [chunk("beta", 0), chunk("gamma", 1)]

    embedder = ChromaEmbedder()
    store_chunks(first, embedder, client, "documents")
    store_chunks(second, embedder, client, "documents")

    collection = client.get_or_create_collection(name="documents")
    assert collection.count() == 2


def _collection(persist):
    client = chromadb.PersistentClient(path=str(persist))
    return client.get_or_create_collection(name="documents")
