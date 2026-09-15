"""Ingestion package: public API re-exported from the pipeline and stage modules."""

from src.domain.models.chunk import Chunk
from src.domain.models.document import (
    DiscoveredDocument,
    DocumentRecord,
    FileState,
    SourceType,
)
from src.ingestion.parsers import (
    BaseParser,
    MarkdownParser,
    ParsedDocument,
    PlainTextParser,
    Section,
)
from src.ingestion.pipeline import (
    PipelineConfig,
    PipelineRun,
    RunStatus,
    load_and_chunk,
    run_pipeline,
)
from src.ingestion.stages.chunk import (
    ChunkingStrategy,
    build_chunks,
    chunk_text,
    chunking_strategy_for,
)
from src.ingestion.stages.clean import clean_text
from src.ingestion.stages.discover import (
    compute_file_hash,
    detect_mime_type,
    get_active_registry_records,
    resolve_file_lifecycles,
    scan_documents,
)
from src.ingestion.stages.embed import ChromaEmbedder, Embedder
from src.ingestion.stages.enrich import enrich_chunks
from src.ingestion.stages.parse import (
    parse_document,
    parse_document_structured,
    register_parser,
)
from src.ingestion.stages.persist import (
    deactivate_old_vector_chunks,
    log_pipeline_run,
    store_chunks,
    update_registry,
)

__all__ = [
    "BaseParser",
    "ChromaEmbedder",
    "Chunk",
    "ChunkingStrategy",
    "DiscoveredDocument",
    "DocumentRecord",
    "Embedder",
    "FileState",
    "MarkdownParser",
    "ParsedDocument",
    "PipelineConfig",
    "PipelineRun",
    "PlainTextParser",
    "RunStatus",
    "Section",
    "SourceType",
    "build_chunks",
    "chunk_text",
    "chunking_strategy_for",
    "clean_text",
    "compute_file_hash",
    "deactivate_old_vector_chunks",
    "detect_mime_type",
    "enrich_chunks",
    "get_active_registry_records",
    "load_and_chunk",
    "log_pipeline_run",
    "parse_document",
    "parse_document_structured",
    "register_parser",
    "resolve_file_lifecycles",
    "run_pipeline",
    "scan_documents",
    "store_chunks",
    "update_registry",
]
