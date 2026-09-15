# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version History

| Version | Feature Domain     | Key Objective |
|---------|--------------------|---------------|
| 0.0.16  | pgvector Persistence | Persistence moved from ChromaDB to PostgreSQL/pgvector; ChromaDB removed |
| 0.0.15  | LlamaIndex Embeddings | HuggingFaceEmbedding (BAAI/bge-small-en-v1.5) via Settings.embed_model |
| 0.0.14  | LlamaIndex Chunking | Document Structure-Based Chunking (MarkdownNodeParser) for markdown; Fixed-Size Chunking (TokenTextSplitter) for others |
| 0.0.13  | LlamaIndex Parsers | Parsers reimplemented on LlamaIndex (SimpleDirectoryReader + MarkdownNodeParser) |
| 0.0.12  | DB Repositories   | Repository layer over SQLAlchemy + pgvector for documents, chunks, runs, embeddings |
| 0.0.11  | DB & Migrations    | PostgreSQL/pgvector via docker-compose; Alembic migration scaffold |
| 0.0.10  | Stage-Based Ingestion | Ingestion split into discrete stages (discover, parse, clean, chunk, enrich, embed, persist) |
| 0.0.9   | Domain Entities    | Dedicated domain model layer (document, chunk); design doc added |
| 0.0.8   | Chunking & Lineage  | Chunk identity, vector metadata payload, and run→doc→chunk lineage; design doc added |
| 0.0.7   | Document Lifecycle & Lineage | Versioned document registry with run lineage; design doc added |
| 0.0.6   | Evaluation Pipeline  | Rank-based retrieval metrics and LLM-as-judge grounding scores |
| 0.0.5   | Retrieval Pipeline | Embed query, vector search, context assembly, and LLM answer generation |
| 0.0.4   | Automated Tests    | Unit, integration, and e2e test suites for ingestion pipeline and API |
| 0.0.3   | Ingestion Pipeline | ChromaDB scan→chunk→embed→store pipeline with pydantic config and Streamlit UI |
| 0.0.2   | Backend API        | Scaffold FastAPI service with document ingestion and query endpoints |
| 0.0.1   | Project Setup      | Initialize project with `uv`, venv, ruff, and core docs |

## [Unreleased]

## [0.0.16] - 2026-09-15

### Changed
- Persistence now targets PostgreSQL/pgvector instead of ChromaDB: registry (`document_records`), vector chunks (`chunks` with `Vector(384)` embedding), and pipeline runs (`pipeline_runs`) via the repository layer
- `run_pipeline` runs in a single DB session: commit on success; on failure the run is rolled back and re-persisted as `FAILED` with `error_message`
- `resolve_file_lifecycles`/`get_active_registry_records` read the active registry from `document_records` through `DocumentRepository.list_active()`
- `RetrievalPipeline` searches pgvector via `EmbeddingRepository.search` (cosine distance, optional tenant filter); `persist_dir`/`collection_name` removed from config, evaluation CLI, and `PipelineConfig`
- Chunk/registry/run writes use `INSERT … ON CONFLICT DO UPDATE` upserts keyed on business IDs (`src/db/repositories/upsert.py`)
- Removed ChromaDB dependency and all `import chromadb`; deleted `data/chroma/`; `Settings.collection_name`/`persist_dir` removed

### Added
- `src/db/mappers.py`: domain-model ↔ ORM converters (`document_to_orm`, `document_from_orm`, `chunk_to_orm`)
- Streamlit app run-history view: "Show Pipeline Runs" button renders recent runs (status badge, duration, new/modified/deleted counts, chunks, error message)
- `tests/conftest.py`: shared Postgres/pgvector schema fixture and per-test table cleanup; integration/unit tests re-pointed from Chroma temp dirs to `db_session`

## [0.0.15] - 2026-09-15

### Changed
- Embed stage reimplemented on LlamaIndex: `Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")`; `ChromaEmbedder.embed_texts()` delegates to `get_text_embedding_batch()` via the global `Settings`
- Replaced Chroma's `DefaultEmbeddingFunction`; the `Embedder` abstract interface is unchanged (pipeline/retrieval callers unaffected)

### Added
- Dependency: `llama-index-embeddings-huggingface` (pulls in `torch`, `transformers`); 384-d embedding model matches `EMBEDDING_DIM=384` in the DB chunk model

## [0.0.14] - 2026-09-15

### Changed
- Chunk stage reimplemented on LlamaIndex: **Document Structure-Based Chunking** (MarkdownNodeParser) for markdown files, **Fixed-Size Chunking** (TokenTextSplitter) for all other formats
- Added `ChunkingStrategy` enum and `chunking_strategy_for()` to select chunking approach by file extension
- Pipeline auto-selects strategy from discovered document's extension; public `build_chunks()` and `chunk_text()` signatures unchanged (accept `strategy=` kwarg)

## [0.0.13] - 2026-09-15

### Changed
- `MarkdownParser` reimplemented on LlamaIndex: text loaded via `SimpleDirectoryReader`, section structure produced by `MarkdownNodeParser` (heading-aware split that ignores headings inside fenced code blocks), then reconstructed into the existing flat `Section` list with hierarchical content scoping
- `PlainTextParser` now loads text and file metadata through `SimpleDirectoryReader` (no structural extraction)
- Added `src/ingestion/parsers/_loaders.py` shared LlamaIndex loader; public `BaseParser`/`ParsedDocument`/`Section` API and the extension-based parser dispatcher are unchanged

### Added
- Dependency: `llama-index-core`
- Parser metadata now includes LlamaIndex file info (`file_path`, `file_name`, `file_type`, `file_size`, `creation_date`, `last_modified_date`)

## [0.0.12] - 2026-09-14

### Added
- Repository layer (`src/db/repositories/`): `DocumentRepository` (versioned document registry CRUD + lifecycle), `ChunkRepository` (chunk CRUD, doc/version deactivation, active counts), `RunRepository` (pipeline run CRUD + finalization), `EmbeddingRepository` (pgvector store + cosine-distance search)
- ORM models (`src/db/models.py`): `DocumentRecord`, `Chunk` (with `Vector(384)` embedding), `PipelineRun`, `RunEvent` — registered on `Base.metadata` for Alembic autogenerate
- `src/db/session.py`: engine, `SessionLocal`, FastAPI `get_db()` dependency, and `session_scope()` context manager
- `src/db/base.py`: `Base` with named-constraint conventions moved from `models.py`; `TimestampMixin` (`created_at`/`updated_at`)
- Pydantic app schemas (`src/db/schemas/app/`): `documents.py`, `chunks.py`, `pipeline_runs.py`, `run_events.py` with Create/Read DTOs
- Dependency: `pgvector`

### Changed
- `src/db/__init__.py` now re-exports models; `src/db/models.py` is the model registry importing `Base` from `src/db/base.py`

## [0.0.11] - 2026-09-14

### Added
- PostgreSQL/pgvector via `docker-compose.yml` (`pgvector/pgvector:pg16`, port 5432, named volume, healthcheck)
- Alembic migration scaffold: `alembic.ini`, `src/db/` package with `models.py` (`Base`) and `migrations/` (`env.py`, `script.py.mako`, empty `versions/`)
- `DATABASE_URL` setting in `src/config.py` and `.env.example`
- Dependencies: `sqlalchemy`, `alembic`, `psycopg[binary]`

### Changed
- `src/db/migrations/env.py` reads the connection URL from application settings and enables batch mode outside production

## [0.0.10] - 2026-09-14

### Added
- Stage-based ingestion pipeline (`src/ingestion/stages/`): `discover` (filesystem scan, fingerprint, lifecycle resolution), `parse` (raw text loading), `clean` (text normalization), `chunk` (content splitting), `enrich` (document metadata injection), `embed` (embedding abstraction), `persist` (registry/vector/run-log writes)

### Changed
- `src/ingestion/pipeline.py` refactored into a thin orchestrator that runs the stages in order; lifecycle resolution no longer writes the registry — the orchestrator persists it after discovery
- Public API unchanged: `src/ingestion/__init__.py` re-exports stage functions alongside the pipeline models and composite `load_and_chunk`

## [0.0.9] - 2026-09-14

### Added
- Domain entities design (`docs/design-domain-entities.md`): entity catalogue, relationships, invariants, and the layering rationale for a dedicated domain model package
- Dedicated domain model layer (`src/domain/models/`): `document.py` (`SourceType`, `FileState`, `DiscoveredDocument`, `DocumentRecord`) and `chunk.py` (`Chunk`)

### Changed
- Moved `src/ingestion.py` → `src/ingestion/pipeline.py`; new `src/ingestion/__init__.py` re-exports the public API so downstream imports are unchanged
- `Chunk` and document models moved out of the pipeline module into `src/domain/models/`; pipeline imports and re-exports them
- Removed the redundant `src/models/` package in favour of the domain models package

## [0.0.8] - 2026-09-14

### Added
- Chunking and lineage design (`docs/design-chunk-and-lineage.md`): chunk identity (`relative_path:version_tag:index`), the vector metadata payload, and the `run_id → doc_id → version_tag → chunk_index` lineage chain

### Fixed
- Metadata merge order in `DocumentRecord.model_post_init`: system fields now always reflect the record's own version (previously stale `prev_meta` overrode `doc_id`/`version`/`is_active`, corrupting v2 records, chunk IDs, and deletion toggles)

### Changed
- `Chunk.text` renamed to `Chunk.content`; `DocumentRecord` now embeds a `DiscoveredDocument` for raw file metadata
- Ported unit/integration tests to the new `Chunk`/`DocumentRecord`/`DiscoveredDocument` API; e2e document listing assertion made tolerant to repo content

## [0.0.7] - 2026-09-14

### Added
- Document lifecycle and lineage design (`docs/design-document-lifecycle-and-lineage.md`): lifecycle states (new/unchanged/modified/deleted), per-file versioning, chunk lineage via run/dataset/version identifiers, and multitenancy-aware retrieval
- Versioned ingestion pipeline (`src/ingestion.py`): registry-based lifecycle resolution, run logging to `pipeline_runs`, soft-delete of superseded versions
- Incremental ingestion semantics: a no-op run produces zero chunks and records the run

### Changed
- `PipelineConfig` now defaults from `src/config.py` settings (single source of truth)
- `logging.basicConfig` moved out of module import and into the CLI `main()` to avoid import-time side effects

### Fixed
- `src/retrieval.py` reads the new `relative_path`/`chunk_index` metadata keys (with fallback to legacy keys) and filters results on `is_active`, plus optional `tenant_id`
- Updated `src/app.py`, `src/api.py`, and all tests to the new ingestion API; e2e ingest test is now hermetic and asserts idempotency

## [0.0.6] - 2026-09-14

### Added
- Evaluation pipeline (`src/evaluation.py`): rank-based retrieval metrics (MRR, hit rate, precision@k, recall@k) and LLM-as-judge answer grounding scores
- Pydantic schemas for evaluation (`EvalCase`, `RankingMetrics`, `CaseResult`, `RetrievalEvaluation`, `Judgement`)
- `Judge` abstraction with OpenAI-compatible LLM rubric judge and offline stub; `--cases` JSONL CLI for evaluating retrieval

## [0.0.5] - 2026-09-14

### Added
- Retrieval pipeline (`src/retrieval.py`): embed query → vector search → context assembly → LLM generation
- Pydantic schemas for retrieval and generation (`Query`, `RetrievedChunk`, `RetrievalResult`, `GenerationResult`)
- `LLM` abstraction with OpenAI-compatible client and offline stub; `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT` settings

## [0.0.4] - 2026-09-14

### Added
- Unit tests for ingestion (`tests/unit/`)
- Integration tests for the ChromaDB pipeline (`tests/integration/`)
- End-to-end API tests (`tests/e2e/`)
- `pytest` and `httpx` dev dependencies and pytest config in `pyproject.toml`

## [0.0.3] - 2026-09-14

### Added
- ChromaDB ingestion pipeline (`src/ingestion.py`): scan `data/raw` → load & chunk → embed → store
- `src/config.py` with pydantic-settings, reading all config from `.env`
- Minimal Streamlit app (`src/app.py`); added `streamlit` dependency
- Added `chromadb`, `pydantic-settings` dependencies

### Changed
- `Chunk` is now a pydantic `BaseModel`; settings loaded via pydantic-settings
- `src/api.py` uses pydantic response models (`HealthResponse`, `IngestResponse`)
- Renamed `src/pipeline.py` to `src/ingestion.py`

## [0.0.2] - 2026-09-14

### Added
- Scaffolded FastAPI project (`src/app.py`, `src/api.py`, `src/ingestion.py`)
- In-memory `data/raw/*.md` ingestion and `/health`, `/documents`, `/ingest` endpoints
- `.env`, `.env.example`, and `data/raw/SOP-FIN-004.md`

## [0.0.1] - 2026-09-14

### Added
- Init project with `uv --bare`
- Virtual environment, `ruff` dev dependency
- `README.md`, `CHANGELOG.md`, Python `.gitignore`

[0.0.16]: https://github.com/mezni/rag-project/releases/tag/v0.0.16
[0.0.15]: https://github.com/mezni/rag-project/releases/tag/v0.0.15
[0.0.14]: https://github.com/mezni/rag-project/releases/tag/v0.0.14
[0.0.13]: https://github.com/mezni/rag-project/releases/tag/v0.0.13
[0.0.12]: https://github.com/mezni/rag-project/releases/tag/v0.0.12
[0.0.11]: https://github.com/mezni/rag-project/releases/tag/v0.0.11
[0.0.10]: https://github.com/mezni/rag-project/releases/tag/v0.0.10
[0.0.9]: https://github.com/mezni/rag-project/releases/tag/v0.0.9
[0.0.8]: https://github.com/mezni/rag-project/releases/tag/v0.0.8
[0.0.7]: https://github.com/mezni/rag-project/releases/tag/v0.0.7
[0.0.6]: https://github.com/mezni/rag-project/releases/tag/v0.0.6
[0.0.5]: https://github.com/mezni/rag-project/releases/tag/v0.0.5
[0.0.4]: https://github.com/mezni/rag-project/releases/tag/v0.0.4
[0.0.3]: https://github.com/mezni/rag-project/releases/tag/v0.0.3
[0.0.2]: https://github.com/mezni/rag-project/releases/tag/v0.0.2
[0.0.1]: https://github.com/mezni/rag-project/releases/tag/v0.0.1