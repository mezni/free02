"""Unit tests for src/ingestion text and document processing."""

from pathlib import Path

from src.ingestion import (
    DocumentRecord,
    FileState,
    PipelineConfig,
    SourceType,
    chunk_text,
    load_and_chunk,
    scan_documents,
)


def _record(path: str) -> DocumentRecord:
    return DocumentRecord(
        doc_id=f"{path}:v1",
        file_name=Path(path).name,
        relative_path=path,
        parent_directory=str(Path(path).parent),
        file_extension=Path(path).suffix.lower(),
        mime_type="text/markdown",
        source=SourceType.FILESYSTEM,
        version=1,
        version_tag="v1",
        file_hash="hash",
        is_active=True,
        state=FileState.NEW,
        size_bytes=1,
        modified_at=1.0,
    )


def test_scan_documents_finds_markdown_and_text(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text("one", encoding="utf-8")
    (raw / "b.txt").write_text("two", encoding="utf-8")
    (raw / "nested").mkdir()
    (raw / "nested" / "c.md").write_text("three", encoding="utf-8")
    (raw / "skip.log").write_text("four", encoding="utf-8")

    found = scan_documents(raw)

    assert [p.name for p in found] == ["a.md", "b.txt", "c.md"]


def test_scan_documents_empty_dir(tmp_path):
    assert scan_documents(tmp_path) == []


def test_chunk_text_keeps_small_text_whole():
    text = "first\n\nsecond"
    assert chunk_text(text, chunk_size=1000, overlap=0) == ["first\n\nsecond"]


def test_chunk_text_splits_large_text():
    first = "paragraph-zero " * 50
    rest = "paragraph-one " * 50
    text = f"{first}\n\n{rest}"

    chunks = chunk_text(text, chunk_size=80, overlap=0)

    assert len(chunks) == 2
    assert chunks[0].startswith("paragraph-zero")
    assert chunks[1].startswith("paragraph-one")


def test_chunk_text_applies_overlap():
    text = ("x" * 90) + "\n\n" + ("y" * 90) + "\n\n" + ("z" * 90)

    chunks = chunk_text(text, chunk_size=100, overlap=30)

    assert len(chunks) == 3
    assert chunks[1].startswith(chunks[0][-30:])


def test_load_and_chunk_exposes_ids_and_metadata(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text("para-a\n\npara-b\n\npara-c", encoding="utf-8")
    config = PipelineConfig(raw_dir=raw)

    chunks = load_and_chunk(_record("doc.md"), config, run_id="run-1")

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].doc_id == "doc.md:v1"
    assert chunks[0].id == "doc.md:v1:0"
    assert chunks[0].doc_metadata["relative_path"] == "doc.md"
