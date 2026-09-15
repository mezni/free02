# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version History

| Version | Feature Domain     | Key Objective |
|---------|--------------------|---------------|
| 0.0.7   | Document Lifecycle & Lineage | Versioned document registry with run lineage; design doc added |
| 0.0.6   | Evaluation Pipeline  | Rank-based retrieval metrics and LLM-as-judge grounding scores |
| 0.0.5   | Retrieval Pipeline | Embed query, vector search, context assembly, and LLM answer generation |
| 0.0.4   | Automated Tests    | Unit, integration, and e2e test suites for ingestion pipeline and API |
| 0.0.3   | Ingestion Pipeline | ChromaDB scan→chunk→embed→store pipeline with pydantic config and Streamlit UI |
| 0.0.2   | Backend API        | Scaffold FastAPI service with document ingestion and query endpoints |
| 0.0.1   | Project Setup      | Initialize project with `uv`, venv, ruff, and core docs |

## [Unreleased]

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

[0.0.7]: https://github.com/mezni/rag-project/releases/tag/v0.0.7
[0.0.6]: https://github.com/mezni/rag-project/releases/tag/v0.0.6
[0.0.5]: https://github.com/mezni/rag-project/releases/tag/v0.0.5
[0.0.4]: https://github.com/mezni/rag-project/releases/tag/v0.0.4
[0.0.3]: https://github.com/mezni/rag-project/releases/tag/v0.0.3
[0.0.2]: https://github.com/mezni/rag-project/releases/tag/v0.0.2
[0.0.1]: https://github.com/mezni/rag-project/releases/tag/v0.0.1