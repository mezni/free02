# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ChromaDB ingestion pipeline (`src/ingestion.py`): scan `data/raw` → load & chunk → embed → store
- `src/config.py` with pydantic-settings, reading all config from `.env`
- Minimal Streamlit app (`src/app.py`); added `streamlit` dependency
- Added `chromadb`, `pydantic-settings` dependencies

### Changed
- `Chunk` is now a pydantic `BaseModel`; settings loaded via pydantic-settings
- `src/api.py` uses pydantic response models (`HealthResponse`, `IngestResponse`)
- Renamed `src/pipeline.py` to `src/ingestion.py`

## Version History

| Version | Feature Domain | Key Objective |
|---------|----------------|---------------|
| 0.0.2   | Backend API    | Scaffold FastAPI service with document ingestion and query endpoints |
| 0.0.1   | Project Setup  | Initialize project with `uv`, venv, ruff, and core docs |

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

[0.0.2]: https://github.com/mezni/rag-project/releases/tag/v0.0.2
[0.0.1]: https://github.com/mezni/rag-project/releases/tag/v0.0.1