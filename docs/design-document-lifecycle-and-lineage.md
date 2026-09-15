# Design: Document Lifecycle and Lineage

Status: accepted · Applies to: `src/ingestion.py`, `src/retrieval.py`

## Overview

Documents are treated as versioned first-class entities rather than static
files. The ingestion pipeline resolves a source directory on disk against a
persistent registry, derives per-file lifecycle transitions, versions changed
documents, and records every run so each stored chunk can be traced back to the
document version that produced it.

Two cross-cutting concerns drive the design:

- **Lifecycle** — files move through `new → active`, `modified → version bump`,
  and `deleted → deactivated` transitions.
- **Lineage** — every chunk and registry record carries enough identifiers
  (`run_id`, `doc_id`, `version_tag`, `chunk_index`) to reconstruct where it
  came from and when.

## Lifecycle States

A source file on disk maps to one or more registry records over time. The
current state of the newest version of a file is the "active" record.

| FileState | Meaning                                              | Active? |
|-----------|------------------------------------------------------|---------|
| `NEW`     | First-seen file, stored as `v1`                      | yes     |
| `UNCHANGED` | File hash matches the active registry record       | yes     |
| `MODIFIED` | Content hash differs → previous version deactivated, new version stored | new version yes, old no |
| `DELETED` | File gone from disk → active record deactivated      | no      |

State is derived purely from two inputs: the current set of files on disk
(hashed with MD5) and the active records in the registry.

### Versioning

- A document's identity is `relative_path`.
- Each stored version gets `version` (integer, starting at 1) and
  `version_tag` (e.g. `v1`, `v2`).
- The registry `doc_id` is `{relative_path}:{version_tag}`; chunk `id` is
  `{relative_path}:{version_tag}:{index}`.
- Old versions are kept but flagged `is_active=False`; they remain available for
  audit, but are excluded from retrieval.

## Lineage

Every artifact in the pipeline records its provenance:

```
pipeline_runs  ──run_id──▶  registry records (document versions)
                                │
                                └─relative_path + version_tag ──▶ chunks
```

| Artifact    | Identifiers tracked                                  |
|-------------|------------------------------------------------------|
| `PipelineRun` | `run_id`, source, timestamps, per-state file counts, `chunks_created`, error |
| `DocumentRecord` | `doc_id`, `version_tag`, `file_hash`, `state`, timestamps |
| `Chunk` | `run_id`, `doc_id`, `chunk_index`, `doc_metadata` (full record dict) |

Consequences:

- Reproducibility: a chunk's exact source document version is known at all times.
- Traceability: `pipeline_runs` records who/what ran when and how much work was done.
- Rollback: deactivating a version is a metadata toggle; the vectors remain.

## Collections

The persistence directory contains three Chroma collections:

| Collection             | Purpose                          | Writes                          | Reads                             |
|------------------------|----------------------------------|---------------------------------|-----------------------------------|
| `documents`            | Vector store for searchable chunks | `store_chunks()`, `deactivate_old_vector_chunks()` | `RetrievalPipeline.search()` (via `where`) |
| `documents_registry`   | Document lifecycle/version registry | `update_registry()`             | `resolve_file_lifecycles()`       |
| `pipeline_runs`        | Run/audit log                    | `log_pipeline_run()`             | —                                 |

Upsert semantics keep the registry idempotent: re-running a pipeline with no
changes yields zero new chunks.

## Lifecycle Resolution Algorithm

`resolve_file_lifecycles()` computes transitions in three passes:

1. **New files** — present on disk, absent from registry → `NEW` at `v1`.
2. **Modified files** — present on disk, hash differs from the active record →
   deactivate the old version (`MODIFIED`) and create the next version.
3. **Deleted files** — present in registry but absent from disk → deactivate
   the active record (`DELETED`).

Deactivated registry records are upserted with `is_active=False`;
`deactivate_old_vector_chunks()` applies the same toggle to the corresponding
stored vectors so search excludes them.

## Retrieval Integration

`src/retrieval.py` always filters results with `where={"is_active": True}`,
optionally combined with a `tenant_id` for multitenancy isolation:

```python
Query(text=..., tenant_id="acme")  # filters [{"is_active": True}, {"tenant_id": "acme"}]
```

## Metadata & Multitenancy

Each `DocumentRecord` carries tenant, RBAC, and descriptive attributes that are
flattened into Chroma-compatible metadata by `to_dict()`:

- `tenant_id` — customer/tenant boundary.
- `access_roles` — flattened to a comma-separated scalar (Chroma requires scalars).
- `classification`, `department`, `category`, `doc_type`, `language`.
- `title`, `author`, `document_summary`, `total_pages` (optionals, defaulted to
  empty/zero for Chroma scalar compatibility).

Custom metadata can be merged via the `metadata` dict when a record is built.

## Design Decisions

- **Registry in Chroma, not SQL** — keeps a single persistence dependency; the
  registry is a normal collection keyed by `doc_id`.
- **Content hash (MD5) over mtime** — detects true content changes and is robust
  to copy operations that preserve timestamps. MD5 is sufficient for change
  detection (not security).
- **Soft-delete via `is_active`** — preserves history cheaply and supports
  point-in-time lineage without destructive deletes.
- **Incremental by default** — a no-op run produces no chunks and records the run
  with all counts at zero.

## Open Questions

- Cross-tenant access control is present in metadata and enforced at query time
  only when `Query.tenant_id` is supplied; there is no auth layer deciding who
  may pass which `tenant_id`.
- The registry keyed by `relative_path` today; renaming a file is treated as
  delete + new. A stable external document ID would preserve lineage across renames.
- `pipeline_runs` has no pruning policy; long-lived installations should plan for
  growth or periodic compaction.