"""Unit tests for src/ingestion/stages processors."""

import hashlib
from pathlib import Path

import chromadb
import pytest

from src.domain.models.chunk import Chunk
from src.ingestion import (
    ChromaEmbedder,
    DiscoveredDocument,
    DocumentRecord,
    FileState,
    PipelineConfig,
    PipelineRun,
    RunStatus,
    SourceType,
    build_chunks,
    chunk_text,
    clean_text,
    compute_file_hash,
    deactivate_old_vector_chunks,
    detect_mime_type,
    enrich_chunks,
    get_active_registry_records,
    log_pipeline_run,
    parse_document,
    resolve_file_lifecycles,
    store_chunks,
    update_registry,
)
from src.ingestion.stages.parse import load_raw_text


class _IdentityEmbedder:
    """Deterministic, dependency-free embedder for unit tests."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(offset + index) for index in range(8)]
            for offset in range(len(texts))
        ]


def _record(path: str, state: FileState = FileState.NEW) -> DocumentRecord:
    return DocumentRecord(
        doc_id=f"{path}:v1",
        version=1,
        version_tag="v1",
        state=state,
        discovered_doc=DiscoveredDocument(
            relative_path=path,
            file_name=Path(path).name,
            parent_directory=str(Path(path).parent),
            file_extension=Path(path).suffix.lower(),
            mime_type="text/markdown",
            file_hash="hash",
            size_bytes=1,
            modified_at=1.0,
            source=SourceType.FILESYSTEM,
        ),
    )


def _chunk(text: str, index: int) -> Chunk:
    return Chunk(
        content=text,
        run_id="run-1",
        doc_id="doc.md:v1",
        index=index,
        doc_metadata={
            "relative_path": "doc.md",
            "version": 1,
            "version_tag": "v1",
            "is_active": True,
        },
    )


# --- Parse stage ---


def test_load_raw_text_reads_utf8(tmp_path):
    file_path = tmp_path / "doc.md"
    file_path.write_text("héllo world", encoding="utf-8")

    assert load_raw_text(file_path) == "héllo world"


def test_parse_document_loads_discovered_file(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text("content", encoding="utf-8")
    discovered = _record("doc.md").discovered_doc

    assert parse_document(discovered, raw) == "content"


# --- Clean stage ---


def test_clean_text_strips_bom_and_normalizes_newlines():
    assert clean_text("\ufeffa\r\nb\rc") == "a\nb\nc"


def test_clean_text_preserves_paragraph_separators():
    assert clean_text("a\n\nb\n\nc") == "a\n\nb\n\nc"


def test_chunk_text_rejects_overlap_gt_chunk_size():
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("x" * 50, chunk_size=20, overlap=21)


def test_chunk_text_accepts_overlap_eq_chunk_size():
    chunks = chunk_text("hello world foo bar baz", chunk_size=5, overlap=5)
    assert len(chunks) >= 1


# --- Chunk stage ---


def test_build_chunks_assigns_indices_and_ids():
    chunks = build_chunks(
        "first second",
        doc_id="doc.md:v1",
        run_id="run-1",
        chunk_size=3,
        overlap=0,
    )

    assert [chunk.index for chunk in chunks] == [0, 1]
    assert all(chunk.run_id == "run-1" for chunk in chunks)
    assert all(chunk.doc_id == "doc.md:v1" for chunk in chunks)


def test_build_chunks_creates_chunk_ids_from_metadata():
    chunks = build_chunks(
        "a b", doc_id="doc.md:v1", run_id="run-1", chunk_size=3, overlap=0
    )

    assert chunks[0].doc_metadata == {}
    assert [chunk.id for chunk in chunks] == ["file:v1:0", "file:v1:1"]


# --- Enrich stage ---


def test_enrich_chunks_injects_document_metadata():
    doc_rec = _record("doc.md")
    chunks = build_chunks(
        "a\n\nb", doc_rec.doc_id, run_id="run-1", chunk_size=1000, overlap=0
    )

    enriched = enrich_chunks(chunks, doc_rec)

    assert all(chunk.doc_metadata["relative_path"] == "doc.md" for chunk in enriched)
    assert all(chunk.doc_metadata["version_tag"] == "v1" for chunk in enriched)
    assert chunks[0].doc_metadata == {}  # enrichment does not mutate the source


# --- Discover stage ---


def test_compute_file_hash_is_content_based(tmp_path):
    file_path = tmp_path / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    assert compute_file_hash(file_path) == hashlib.md5(b"hello").hexdigest()

    file_path.write_text("changed", encoding="utf-8")
    assert compute_file_hash(file_path) != hashlib.md5(b"hello").hexdigest()


def test_detect_mime_type_covers_markdown_text_and_unknown(tmp_path):
    md = tmp_path / "doc.md"
    txt = tmp_path / "doc.txt"
    unknown = tmp_path / "docfile"
    md.touch()
    txt.touch()
    unknown.touch()

    assert detect_mime_type(md) == "text/markdown"
    assert detect_mime_type(txt) == "text/plain"
    assert detect_mime_type(unknown) == "text/plain"


def test_get_active_registry_records_filters_inactive(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_or_create_collection(name="documents_registry")
    collection.upsert(
        ids=["doc.md:v1", "other.md:v1"],
        documents=["a", "b"],
        metadatas=[
            {"relative_path": "doc.md", "is_active": True},
            {"relative_path": "other.md", "is_active": False},
        ],
    )

    active = get_active_registry_records(client, "documents_registry")

    assert set(active) == {"doc.md"}


def test_resolve_lifecycles_marks_new_files(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text("alpha", encoding="utf-8")
    (raw / "b.md").write_text("beta", encoding="utf-8")
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))

    new_active, deactivated, unchanged = resolve_file_lifecycles(
        PipelineConfig(raw_dir=raw, persist_dir=tmp_path / "chroma"), client
    )

    assert {rec.state for rec in new_active} == {FileState.NEW}
    assert {rec.doc_id for rec in new_active} == {"a.md:v1", "b.md:v1"}
    assert deactivated == []
    assert unchanged == []


def test_resolve_lifecycles_detects_modification_and_deletion(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    persist = tmp_path / "chroma"
    client = chromadb.PersistentClient(path=str(persist))

    (raw / "doc.md").write_text("alpha", encoding="utf-8")
    (raw / "stable.md").write_text("stable", encoding="utf-8")
    (raw / "gone.md").write_text("gone", encoding="utf-8")

    registry = client.get_or_create_collection(name="documents_registry")
    seed_records = [
        DocumentRecord(
            doc_id=f"{name}:v1",
            version=1,
            version_tag="v1",
            state=FileState.NEW,
            discovered_doc=DiscoveredDocument(
                relative_path=name,
                file_name=name,
                parent_directory=".",
                file_extension=".md",
                mime_type="text/markdown",
                file_hash=compute_file_hash(raw / name),
                size_bytes=(raw / name).stat().st_size,
                modified_at=(raw / name).stat().st_mtime,
                source=SourceType.FILESYSTEM,
            ),
        )
        for name in ("doc.md", "stable.md", "gone.md")
    ]
    update_registry(registry, seed_records)

    (raw / "doc.md").write_text("alpha changed", encoding="utf-8")
    (raw / "gone.md").unlink()

    new_active, deactivated, unchanged = resolve_file_lifecycles(
        PipelineConfig(raw_dir=raw, persist_dir=persist), client
    )

    assert {rec.doc_id for rec in new_active} == {"doc.md:v2"}
    assert new_active[0].state == FileState.MODIFIED
    assert {rec.doc_id for rec in deactivated} == {"doc.md:v1", "gone.md:v1"}
    assert {
        rec.state
        for rec in deactivated
        if rec.discovered_doc.relative_path == "gone.md"
    } == {FileState.DELETED}
    assert {rec.doc_id for rec in unchanged} == {"stable.md:v1"}
    assert unchanged[0].state == FileState.UNCHANGED


# --- Embed stage ---


def test_chroma_embedder_returns_embeddings():
    embedder = ChromaEmbedder()

    embeddings = embedder.embed_texts(["hello", "world"])

    assert len(embeddings) == 2
    assert all(len(vector) == len(embeddings[0]) for vector in embeddings)


# --- Persist stage ---


def test_update_registry_upserts_records(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_or_create_collection(name="documents_registry")

    update_registry(collection, [_record("doc.md")])

    result = collection.get(ids=["doc.md:v1"])
    assert result["metadatas"][0]["relative_path"] == "doc.md"
    assert result["metadatas"][0]["is_active"] is True


def test_store_chunks_embeds_and_persists(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))

    count = store_chunks(
        [_chunk("alpha", 0), _chunk("beta", 1)],
        _IdentityEmbedder(),
        client,
        "documents",
    )

    assert count == 2
    collection = client.get_or_create_collection(name="documents")
    assert collection.count() == 2
    assert {
        meta["relative_path"]
        for meta in collection.get(include=["metadatas"])["metadatas"]
    } == {"doc.md"}


def test_deactivate_old_vector_chunks_flips_active_flag(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    store_chunks(
        [_chunk("alpha", 0), _chunk("beta", 1)],
        _IdentityEmbedder(),
        client,
        "documents",
    )

    deactivate_old_vector_chunks(client, "documents", [_record("doc.md")])

    collection = client.get_or_create_collection(name="documents")
    metadatas = collection.get(include=["metadatas"])["metadatas"]
    assert metadatas
    assert all(meta["is_active"] is False for meta in metadatas)


def test_log_pipeline_run_records_run_metadata(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    run = PipelineRun(source=SourceType.FILESYSTEM, status=RunStatus.SUCCESS)
    run.files_new = 1
    run.chunks_created = 2

    log_pipeline_run(client, run, "pipeline_runs")

    collection = client.get_or_create_collection(name="pipeline_runs")
    result = collection.get(ids=[run.run_id])
    assert result["metadatas"][0]["status"] == "success"
    assert result["metadatas"][0]["chunks_created"] == 2
