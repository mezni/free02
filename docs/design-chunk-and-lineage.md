# Design: Chunking and Lineage

Status: accepted · Applies to: `src/ingestion.py`, `src/retrieval.py`

## Overview

Documents are broken into overlapping chunks before being embedded and stored
in the vector store. Each chunk carries a stable identity and a metadata payload
that lets it be traced back to the exact document version and pipeline run that
produced it. This document covers the chunk schema, chunk identity, the vector
metadata payload, and the `run → doc → chunk` lineage chain.

This design complements
[`docs/design-document-lifecycle-and-lineage.md`](design-document-lifecycle-and-lineage.md),
which covers document lifecycle and versioning.

## Chunk Record

A `Chunk` is a pydantic model with four provenance fields plus injected
document metadata:

| Field          | Type     | Purpose                                             |
|----------------|----------|-----------------------------------------------------|
| `content`      | `str`    | The chunk text (embedded and stored as the vector document) |
| `run_id`       | `str`    | The pipeline run that created this chunk            |
| `doc_id`       | `str`    | The document version this chunk belongs to (e.g. `billing.md:v2`) |
| `index`        | `int`    | Position of the chunk within the document (0-based) |
| `doc_metadata` | `dict`   | The full flattened document metadata payload        |

### Chunk identity

Chunk IDs are deterministic and version-scoped:

```
{relative_path}:{version_tag}:{index}
# e.g. billing/sop.md:v2:3
```

Properties:

- **Stable across re-runs** — re-ingesting an unchanged file produces the same
  IDs, so `upsert` is idempotent and no duplicate vectors accumulate.
- **Version-scoped** — a `v1` and a `v2` chunk with the same index never
  collide; the pipeline can hold multiple versions of the same document
  simultaneously.
- **Human-readable** — the source path and version are directly visible in IDs,
  which aids auditing.

### Vector metadata payload

`get_vector_metadata()` merges the document metadata with chunk-specific
fields for storage in Chroma:

```
{**doc_metadata, "run_id": ..., "chunk_index": index}
```

Notable points:

- The stored payload is the same flattened dict used by the registry
  (`DocumentRecord.to_dict()`), so a chunk is self-describing: `tenant_id`,
  `is_active`, `relative_path`, `version`, `classification`, etc. are all
  queryable without a registry join.
- `chunk_index` mirrors `index` under a name that does not collide with the
  document-level `file_extension`/`version` keys; `retrieval.py` reads
  `chunk_index` (falling back to legacy `index`).
- All values are scalars (lists such as `access_roles` are collapsed to
  comma-separated strings) to satisfy Chroma's metadata constraints.

## Lineage Chain

Every artifact is linked by identifiers:

```
PipelineRun.run_id
   └── Chunk.run_id
DocumentRecord.doc_id  ==  Chunk.doc_id
DocumentRecord.version_tag  (in doc_metadata)  ──▶  Chunk.id
DocumentRecord.relative_path  (in doc_metadata) ──▶  retrieval source
```

Given a retrieved chunk, one can answer:

- **What document?** `relative_path` + `version_tag` in `doc_metadata`.
- **Which version?** `version` + `version_tag`.
- **When and by what run?** `run_id` → join to the `pipeline_runs` collection.
- **Where in the document?** `chunk_index`.

## Chunking Strategy

`chunk_text()` is paragraph-aware: text is split on blank lines, and paragraphs
are accumulated up to `chunk_size` characters, carrying `overlap` trailing
characters into the next chunk to preserve cross-boundary context. Since chunk
IDs embed `index`, re-chunking with different parameters produces different IDs
(clean namespace), but stale chunks from a previous parameterization are not
auto-removed — see Open Questions.

## Retrieval Integration

`retrieval.py` never reads the `documents` collection without a metadata filter:

- Always `is_active: True` — superseded/deleted chunks are excluded.
- Optionally `tenant_id` — multitenancy isolation at query time.

The `source` shown to callers is `relative_path` (the file path), not the
`SourceType` enum value stored under the `source` metadata key.

## Design Decisions

- **Denormalized payload over registry joins** — every chunk carries the full
  document metadata so retrieval/filtering is self-contained.
- **Deterministic IDs enable idempotency** — `upsert` replaces content in place;
  no change detection is required at the vector layer.
- **Soft-delete by flag** — `is_active` toggles keep superseded chunks for audit
  without breaking fast vector lookups.
- **Position-carrying IDs (`index`)** — makes partial re-chunking and
  point-in-time reconstruction of a document feasible.

## Open Questions

- Chunk parameter changes (`chunk_size`/`overlap`) produce a new ID space but
  orphan old vectors; consider a `chunking_signature` in the payload plus a
  cleanup pass.
- A document assembled from its chunks for audit trails would need ordering by
  `index` and filtering on a single `doc_id` — feasible today but not exposed as
  an API.
- Renaming a source file creates a new `relative_path`, i.e. a new lineage root;
  a stable external document ID would preserve lineage across renames (see the
  lifecycle design).