"""Document ingestion: an orchestrator over the stage modules (discover → persist)."""

import argparse
import logging
import time
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import chromadb
from pydantic import BaseModel, Field

from src.config import settings
from src.core.logging import setup_logging
from src.domain.models.chunk import Chunk
from src.domain.models.document import DocumentRecord, FileState, SourceType
from src.ingestion.stages.chunk import build_chunks, chunking_strategy_for
from src.ingestion.stages.clean import clean_text
from src.ingestion.stages.discover import resolve_file_lifecycles
from src.ingestion.stages.embed import ChromaEmbedder, Embedder
from src.ingestion.stages.enrich import enrich_chunks
from src.ingestion.stages.parse import parse_document
from src.ingestion.stages.persist import (
    deactivate_old_vector_chunks,
    log_pipeline_run,
    store_chunks,
    update_registry,
)

logger = logging.getLogger(__name__)


# --- Enums & Configuration ---


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PipelineConfig(BaseModel):
    raw_dir: Path = Field(default=settings.raw_dir)
    persist_dir: Path = Field(default=settings.persist_dir)
    collection_name: str = Field(default=settings.collection_name)
    registry_collection_name: str = Field(default="documents_registry")
    runs_collection_name: str = Field(default="pipeline_runs")
    chunk_size: int = Field(default=settings.chunk_size, gt=0)
    overlap: int = Field(default=settings.overlap, ge=0)
    source: SourceType = Field(default=SourceType.FILESYSTEM)
    recreate: bool = Field(default=False)
    tenant_id: str = Field(default="tenant_acme_corp")
    access_roles: list[str] = Field(
        default_factory=lambda: ["internal_user", "engineering"]
    )
    classification: str = Field(default="internal")
    department: str = Field(default="engineering")
    category: str = Field(default="documentation")


class PipelineRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: SourceType
    status: RunStatus = Field(default=RunStatus.RUNNING)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    files_new: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_unchanged: int = 0
    chunks_created: int = 0
    error_message: str | None = None


# --- Backward-Compatible Composite Helper ---


def load_and_chunk(
    doc_rec: DocumentRecord, config: PipelineConfig, run_id: str
) -> list[Chunk]:
    """Composite stage: parse → clean → chunk → enrich a single document record."""
    text = clean_text(parse_document(doc_rec.discovered_doc, config.raw_dir))
    strategy = chunking_strategy_for(doc_rec.discovered_doc.file_extension)
    raw_chunks = build_chunks(
        text, doc_rec.doc_id, run_id, config.chunk_size, config.overlap,
        strategy=strategy,
    )
    return enrich_chunks(raw_chunks, doc_rec)


# --- Pipeline Orchestrator ---


def run_pipeline(
    config: PipelineConfig,
    embedder: Embedder | None = None,
) -> tuple[PipelineRun, list[Chunk]]:
    run = PipelineRun(source=config.source)
    start_time = time.perf_counter()
    chunks: list[Chunk] = []

    client = chromadb.PersistentClient(path=str(config.persist_dir))
    if config.recreate:
        for existing in client.list_collections():
            if existing.name == config.collection_name:
                client.delete_collection(name=config.collection_name)
                break

    try:
        new_active, deactivated, unchanged = resolve_file_lifecycles(config, client)

        run.files_new = sum(1 for r in new_active if r.state == FileState.NEW)
        run.files_modified = sum(1 for r in new_active if r.state == FileState.MODIFIED)
        run.files_deleted = sum(1 for r in deactivated if r.state == FileState.DELETED)
        run.files_unchanged = len(unchanged)

        registry = client.get_or_create_collection(name=config.registry_collection_name)
        update_registry(registry, [*new_active, *deactivated])

        deactivate_old_vector_chunks(client, config.collection_name, deactivated)

        for doc_rec in new_active:
            chunks.extend(load_and_chunk(doc_rec, config, run.run_id))

        run.chunks_created = len(chunks)
        store_chunks(
            chunks, embedder or ChromaEmbedder(), client, config.collection_name
        )
        run.status = RunStatus.SUCCESS

    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error_message = str(exc)
        logger.exception("Pipeline failed")
        raise

    finally:
        run.completed_at = datetime.now(UTC)
        run.duration_seconds = round(time.perf_counter() - start_time, 3)
        log_pipeline_run(client, run, config.runs_collection_name)
        client.close()

    return run, chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest documents with tenant metadata"
    )
    parser.add_argument("--source", type=SourceType, default=SourceType.FILESYSTEM)
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_dir)
    parser.add_argument("--persist-dir", type=Path, default=settings.persist_dir)
    parser.add_argument("--collection-name", type=str, default=settings.collection_name)
    parser.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    parser.add_argument("--overlap", type=int, default=settings.overlap)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    config = PipelineConfig(
        source=args.source,
        raw_dir=args.raw_dir,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        recreate=args.recreate,
    )

    run, chunks = run_pipeline(config)
    logger.info(
        "Run %s complete | Total Chunks Ingested: %d",
        run.run_id,
        len(chunks),
    )


if __name__ == "__main__":
    main()
