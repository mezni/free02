# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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