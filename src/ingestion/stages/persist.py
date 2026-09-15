"""Persist stage: write document registry, vector chunks, and run logs to Postgres (pgvector)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.db import mappers
from src.db.models import Chunk as ChunkORM
from src.db.models import PipelineRun as PipelineRunORM
from src.db.repositories import (
    ChunkRepository,
    DocumentRepository,
    EmbeddingRepository,
    RunRepository,
)
from src.domain.models.chunk import Chunk
from src.domain.models.document import DocumentRecord
from src.ingestion.stages.embed import Embedder

if TYPE_CHECKING:
    from src.ingestion.pipeline import PipelineRun


def update_registry(session: Session, records: list[DocumentRecord]) -> None:
    """Upsert document-records rows (registry) keyed by ``doc_id``."""
    if not records:
        return
    _registry = DocumentRepository(session)
    for record in records:
        _registry.upsert(mappers.document_to_orm(record))


def store_chunks(
    chunks: list[Chunk],
    embedder: Embedder,
    session: Session,
) -> int:
    """Embed chunk texts and upsert chunk rows with pgvector embeddings."""
    if not chunks:
        return 0

    texts = [chunk.content for chunk in chunks]
    embeddings = embedder.embed_texts(texts)
    _embeddings = EmbeddingRepository(session)
    for chunk, vector in zip(chunks, embeddings):
        _embeddings.upsert(mappers.chunk_to_orm(chunk, vector))
    return len(chunks)


def deactivate_old_vector_chunks(
    session: Session, deactivated_records: list[DocumentRecord]
) -> None:
    """Deactivate chunks belonging to superseded document versions."""
    if not deactivated_records:
        return
    _chunks = ChunkRepository(session)
    for record in deactivated_records:
        _chunks.deactivate_by_doc_version(
            record.discovered_doc.relative_path, record.version
        )


def reset_vector_store(session: Session) -> None:
    """Delete all chunk rows (recreate semantics: wipe the vector store)."""
    session.execute(delete(ChunkORM))


def _run_to_orm(run: PipelineRun) -> PipelineRunORM:
    return PipelineRunORM(
        run_id=run.run_id,
        source=run.source.value if hasattr(run.source, "value") else str(run.source),
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        files_new=run.files_new,
        files_modified=run.files_modified,
        files_deleted=run.files_deleted,
        files_unchanged=run.files_unchanged,
        chunks_created=run.chunks_created,
        error_message=run.error_message,
    )


def log_pipeline_run(session: Session, run: PipelineRun) -> None:
    """Upsert a pipeline-run row keyed by ``run_id``."""
    _runs = RunRepository(session)
    _runs.upsert(_run_to_orm(run))