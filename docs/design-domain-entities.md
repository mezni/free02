# Design: Domain Entities

Status: accepted · Applies to: `src/domain/models/`

## Overview

Domain entities are the canonical data shapes of the system: the things the
ingestion, registry, and retrieval layers agree on. They live in a dedicated
package — `src/domain/models/` — separate from the orchestrating code in
`src/ingestion/pipeline.py`, so the vector store's requirements and the
pipeline's mechanics do not leak into the domain vocabulary.

```
src/
├── domain/
│   └── models/
│       ├── document.py          # SourceType, FileState, DiscoveredDocument, DocumentRecord
│       └── chunk.py             # Chunk
└── ingestion/
    ├── __init__.py              # public API re-exports (ingestion.* namespace unchanged)
    └── pipeline.py              # lifecycle resolution, chunking, embedding, storing
```

## Entity Catalogue

| Entity                | Module                | Role |
|-----------------------|-----------------------|------|
| `SourceType`          | `domain/models/document.py` | Enumerates where a document came from: `filesystem`, `api`, `rdbms` |
| `FileState`           | `domain/models/document.py` | Lifecycle state of a document version: `new`, `unchanged`, `modified`, `deleted` |
| `DiscoveredDocument`  | `domain/models/document.py` | Immutable snapshot of raw source metadata at discovery time (path, hash, size, mime, ...) |
| `DocumentRecord`      | `domain/models/document.py` | Versioned, governance-aware document entity; source of the flattened Chroma metadata |
| `Chunk`               | `domain/models/chunk.py` | A piece of document content plus its provenance identifiers |

## Relationships

```
DiscoveredDocument 1──1 DocumentRecord 1──N Chunk
      (discovered_doc)                (same doc_id/version_tag)
```

- A `DiscoveredDocument` is the factual record of "what we saw on disk".
- A `DocumentRecord` wraps that discovery with versioning, tenancy/RBAC, and
  lifecycle state (`is_active`, `state`, `version_tag`). It is the entity the
  registry collection stores.
- A `Chunk` references a single document version via `doc_id` and copies the
  flattened document metadata into `doc_metadata` for self-contained retrieval.

`chunk.id` is derived, not stored: `{relative_path}:{version_tag}:{index}`.

## Invariants

- **System metadata is authoritative.** `DocumentRecord.model_post_init` builds
  the chroma payload from the record's own fields; custom metadata can only
  *extend* that payload, never override `doc_id`, `version`, `version_tag`,
  `is_active`, `state`, tenancy, or discovery fields.
- **Scalar-only payloads.** Lists (e.g. `access_roles`) are flattened to
  comma-separated strings; optional descriptive fields default to scalar
  placeholders (`""`, `0`) so the payload always satisfies Chroma metadata
  constraints.
- **Identity stability.** Chunk IDs embed `relative_path`/`version_tag`, so
  re-ingesting unchanged data yields identical IDs and `upsert` is idempotent.
- **Lineage completeness.** Every `Chunk` carries `run_id`, `doc_id`, and the
  document metadata, so any stored vector can be traced to a run and a document
  version without a registry join.

## Field Ownership

Two concerns are deliberately kept separate inside `DocumentRecord`:

- **Explicit fields** (`doc_id`, `version`, `tenant_id`, `access_roles`, ...)
  are the entity's typed state — validated by pydantic, used in logic.
- **`metadata`** is the export/extension channel — the flattened payload written
  to the vector store, plus any arbitrary extra keys a caller supplies.

`to_dict()` returns `metadata`, which after `model_post_init` is the
normalized payload. This split avoids having logic read "raw Chroma dicts" and
gives a single export path for both registry records and chunk metadata.

## Design Decisions

- **Dedicated domain package** — entities are shared by ingestion, registry,
  and retrieval; keeping them in one layer prevents import cycles and one
  source of truth for shapes.
- **Record + Discovery split** — separating "who the file is" from "what
  happened to it" makes versioning explicit and keeps listener/API sources
  (`SourceType.API`) on equal footing later.
- **Denormalized chunk payload** — direct, join-free filtering and lineage at
  query time, at the cost of duplicated metadata per chunk (see the chunk and
  lineage design for the trade-off).

## Open Questions

- `PipelineRun`/`RunStatus` still live in `src/ingestion/pipeline.py`; if run
  auditing becomes a cross-cutting concern they could graduate into the domain
  layer too.
- Custom `metadata` values are not recursively validated for scalar-ness; a
  caller could pass a nested structure and fail only at Chroma write time.
- The domain models currently assume document sources are file-based; richer
  `SourceType` handling (API/relational) may require source-specific discovery
  sub-models.