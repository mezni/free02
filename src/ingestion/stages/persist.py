"""Persist stage: write registry records, vector chunks, and run logs to ChromaDB."""

from __future__ import annotations

from typing import TYPE_CHECKING

import chromadb

from src.domain.models.chunk import Chunk
from src.domain.models.document import DocumentRecord
from src.ingestion.stages.embed import Embedder

if TYPE_CHECKING:
    from src.ingestion.pipeline import PipelineRun


def update_registry(
    collection: chromadb.Collection, records: list[DocumentRecord]
) -> None:
    if not records:
        return

    ids = [rec.doc_id for rec in records]
    docs = [
        f"Metadata record for {rec.discovered_doc.relative_path} ({rec.version_tag})"
        for rec in records
    ]
    metadatas = [rec.to_dict() for rec in records]

    collection.upsert(ids=ids, documents=docs, metadatas=metadatas)


def store_chunks(
    chunks: list[Chunk],
    embedder: Embedder,
    client: chromadb.Client,
    collection_name: str,
) -> int:
    if not chunks:
        return 0

    collection = client.get_or_create_collection(name=collection_name)
    ids = [chunk.id for chunk in chunks]
    documents = [chunk.content for chunk in chunks]
    metadatas = [chunk.get_vector_metadata() for chunk in chunks]

    embeddings = embedder.embed_texts(documents)
    collection.upsert(
        ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
    )
    return len(chunks)


def deactivate_old_vector_chunks(
    client: chromadb.Client,
    collection_name: str,
    deactivated_records: list[DocumentRecord],
) -> None:
    if not deactivated_records:
        return

    collection = client.get_or_create_collection(name=collection_name)
    for record in deactivated_records:
        results = collection.get(
            where={
                "$and": [
                    {"relative_path": record.discovered_doc.relative_path},
                    {"version": record.version},
                ]
            }
        )
        if results and results["ids"]:
            chunk_ids = results["ids"]
            updated_metadatas = [
                {**meta, "is_active": False} for meta in results["metadatas"]
            ]
            collection.update(ids=chunk_ids, metadatas=updated_metadatas)


def log_pipeline_run(
    client: chromadb.Client, run: PipelineRun, collection_name: str
) -> None:
    collection = client.get_or_create_collection(name=collection_name)
    summary_text = (
        f"Pipeline Run {run.run_id} | Status: {run.status.value} | "
        f"New: {run.files_new} | Mod: {run.files_modified} | Del: {run.files_deleted}"
    )

    metadata = {
        "run_id": run.run_id,
        "source": run.source.value,
        "status": run.status.value,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else "",
        "duration_seconds": run.duration_seconds or 0.0,
        "files_new": run.files_new,
        "files_modified": run.files_modified,
        "files_deleted": run.files_deleted,
        "files_unchanged": run.files_unchanged,
        "chunks_created": run.chunks_created,
        "error_message": run.error_message or "",
    }

    collection.upsert(ids=[run.run_id], documents=[summary_text], metadatas=[metadata])
