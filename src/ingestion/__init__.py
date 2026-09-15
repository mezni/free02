"""Ingestion package: public API re-exported from the pipeline module."""

from src.domain.models.chunk import Chunk
from src.domain.models.document import (
    DiscoveredDocument,
    DocumentRecord,
    FileState,
    SourceType,
)
from src.ingestion.pipeline import (
    ChromaEmbedder,
    Embedder,
    PipelineConfig,
    PipelineRun,
    RunStatus,
    chunk_text,
    compute_file_hash,
    deactivate_old_vector_chunks,
    detect_mime_type,
    get_active_registry_records,
    load_and_chunk,
    log_pipeline_run,
    resolve_file_lifecycles,
    run_pipeline,
    scan_documents,
    store_chunks,
    update_registry,
)

__all__ = [
    "ChromaEmbedder",
    "Chunk",
    "DiscoveredDocument",
    "DocumentRecord",
    "Embedder",
    "FileState",
    "PipelineConfig",
    "PipelineRun",
    "RunStatus",
    "SourceType",
    "chunk_text",
    "compute_file_hash",
    "deactivate_old_vector_chunks",
    "detect_mime_type",
    "get_active_registry_records",
    "load_and_chunk",
    "log_pipeline_run",
    "resolve_file_lifecycles",
    "run_pipeline",
    "scan_documents",
    "store_chunks",
    "update_registry",
]
