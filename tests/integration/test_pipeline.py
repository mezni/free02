"""Integration tests: end-to-end pipeline into a real Postgres/pgvector store."""

from src.db.models import Chunk as ChunkORM
from src.db.models import PipelineRun as PipelineRunORM
from src.domain.models.chunk import Chunk
from src.ingestion import (
    ChromaEmbedder,
    PipelineConfig,
    run_pipeline,
    store_chunks,
)


def test_run_pipeline_ingests_markdown(tmp_path, db_session):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.md").write_text(
        "\n\n".join(f"# Section {i}\n{'word ' * 50}" for i in range(4)),
        encoding="utf-8",
    )
    config = PipelineConfig(raw_dir=raw)

    run, chunks = run_pipeline(config)

    assert len(chunks) > 1
    assert run.chunks_created == len(chunks)

    rows = db_session.query(ChunkORM).all()
    assert len(rows) == len(chunks)
    assert {row.relative_path for row in rows} == {"doc.md"}

    run_row = db_session.get(PipelineRunORM, run.run_id)
    assert run_row is not None
    assert run_row.status == "success"
    assert run_row.chunks_created == len(chunks)


def test_run_pipeline_recreate_wipes_previous_data(tmp_path, db_session):
    raw = tmp_path / "raw"
    raw.mkdir()
    config = PipelineConfig(raw_dir=raw)

    (raw / "a.md").write_text("hello", encoding="utf-8")
    run_pipeline(config)
    (raw / "a.md").unlink()
    (raw / "b.md").write_text("world", encoding="utf-8")
    run_pipeline(PipelineConfig(raw_dir=raw, recreate=True))

    rows = db_session.query(ChunkORM).all()
    assert len(rows) == 1
    assert {row.relative_path for row in rows} == {"b.md"}


def test_store_chunks_upserts(db_session):
    def chunk(text: str, index: int) -> Chunk:
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

    first = [chunk("alpha", 0)]
    second = [chunk("beta", 0), chunk("gamma", 1)]

    embedder = ChromaEmbedder()
    store_chunks(first, embedder, db_session)
    db_session.commit()
    store_chunks(second, embedder, db_session)
    db_session.commit()

    assert db_session.query(ChunkORM).count() == 2