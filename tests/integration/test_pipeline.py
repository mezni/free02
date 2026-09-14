"""Integration tests: end-to-end pipeline into a real ChromaDB store."""

import chromadb

from src.ingestion import ChromaEmbedder, Chunk, run_pipeline, store


def test_run_pipeline_ingests_markdown(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text(
        ("word " * 200) + "\n\n" + ("zebra " * 200), encoding="utf-8"
    )
    persist = tmp_path / "chroma"

    chunks = run_pipeline(raw_dir=raw, persist_dir=persist)

    assert len(chunks) > 1
    assert persist.exists()

    collection = _collection(persist)
    assert collection.count() == len(chunks)
    sources = {
        meta["source"] for meta in collection.get(include=["metadatas"])["metadatas"]
    }
    assert sources == {"doc.md"}


def test_run_pipeline_recreate_wipes_previous_data(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    persist = tmp_path / "chroma"

    (raw / "a.md").write_text("hello", encoding="utf-8")
    run_pipeline(raw_dir=raw, persist_dir=persist)
    (raw / "a.md").unlink()
    (raw / "b.md").write_text("world", encoding="utf-8")
    run_pipeline(raw_dir=raw, persist_dir=persist, recreate=True)

    collection = _collection(persist)
    assert collection.count() == 1
    assert {
        meta["source"] for meta in collection.get(include=["metadatas"])["metadatas"]
    } == {"b.md"}


def test_chromadb_store_upserts_chunks(tmp_path):
    persist = tmp_path / "chroma"
    client = chromadb.PersistentClient(path=str(persist))

    first = [Chunk(text="alpha", source="doc.md", index=0)]
    second = [
        Chunk(text="beta", source="doc.md", index=0),
        Chunk(text="gamma", source="doc.md", index=1),
    ]

    embedder = ChromaEmbedder()
    store(first, embedder, client)
    store(second, embedder, client)

    collection = client.get_or_create_collection(name="documents")
    assert collection.count() == 2


def _collection(persist):
    client = chromadb.PersistentClient(path=str(persist))
    return client.get_or_create_collection(name="documents")
