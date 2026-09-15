"""Document ingestion: load & chunk → extract metadata dict → embed → store in ChromaDB."""

import argparse
import hashlib
import logging
import mimetypes
import shutil
import time
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pydantic import BaseModel, Field

from src.config import settings
from src.domain.models.chunk import Chunk
from src.domain.models.document import (
    DiscoveredDocument,
    DocumentRecord,
    FileState,
    SourceType,
)

logger = logging.getLogger(__name__)


# --- Enums & Configuration ---


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PipelineConfig(BaseModel):
    raw_dir: Path = Field(default=settings.raw_dir)
    persist_dir: Path = Field(default=settings.persist_dir)
    collection_name: str = Field(default=settings.collection_name)
    registry_collection_name: str = Field(default="documents_registry")
    runs_collection_name: str = Field(default="pipeline_runs")
    chunk_size: int = Field(default=settings.chunk_size, gt=0)
    overlap: int = Field(default=settings.overlap, ge=0)
    source: SourceType = Field(default=SourceType.FILESYSTEM)
    recreate: bool = Field(default=False)


class PipelineRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: SourceType
    status: RunStatus = Field(default=RunStatus.RUNNING)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    files_new: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_unchanged: int = 0
    chunks_created: int = 0
    error_message: str | None = None


# --- Embeddings Abstraction ---


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass


class ChromaEmbedder(Embedder):
    def __init__(self) -> None:
        self._fn = DefaultEmbeddingFunction()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)


# --- Helper Functions ---


def compute_file_hash(path: Path) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        if path.suffix.lower() == ".md":
            return "text/markdown"
        return "text/plain"
    return mime


def scan_documents(raw_dir: Path = settings.raw_dir) -> list[Path]:
    """Return ingestible markdown/text files under `raw_dir`, sorted."""
    if not raw_dir.exists():
        return []
    return sorted(
        path
        for path in raw_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )


def get_active_registry_records(
    client: chromadb.Client, collection_name: str
) -> dict[str, dict]:
    registry = client.get_or_create_collection(name=collection_name)
    results = registry.get(where={"is_active": True})

    active_map = {}
    if results and results["metadatas"]:
        for metadata in results["metadatas"]:
            rel_path = metadata["relative_path"]
            active_map[rel_path] = metadata
    return active_map


# --- Life Cycle & Document Resolution ---


def resolve_file_lifecycles(
    config: PipelineConfig,
    client: chromadb.Client,
) -> tuple[list[DocumentRecord], list[DocumentRecord]]:
    registry_collection = client.get_or_create_collection(
        name=config.registry_collection_name
    )
    active_records = get_active_registry_records(
        client, config.registry_collection_name
    )

    disk_files: dict[str, Path] = {}
    if config.raw_dir.exists():
        for file_path in sorted(config.raw_dir.glob("**/*")):
            if file_path.is_file() and file_path.suffix.lower() in [".md", ".txt"]:
                rel_path = str(file_path.relative_to(config.raw_dir))
                disk_files[rel_path] = file_path

    new_active_records: list[DocumentRecord] = []
    records_to_deactivate: list[DocumentRecord] = []

    for rel_path, file_path in disk_files.items():
        stat = file_path.stat()
        current_hash = compute_file_hash(file_path)
        mime_type = detect_mime_type(file_path)
        parent_dir = str(file_path.relative_to(config.raw_dir).parent)

        discovered = DiscoveredDocument(
            relative_path=rel_path,
            file_name=file_path.name,
            parent_directory=parent_dir,
            file_extension=file_path.suffix.lower(),
            mime_type=mime_type,
            file_hash=current_hash,
            size_bytes=stat.st_size,
            modified_at=stat.st_mtime,
            source=config.source,
        )

        if rel_path not in active_records:
            record = DocumentRecord(
                doc_id=f"{rel_path}:v1",
                state=FileState.NEW,
                discovered_doc=discovered,
                tenant_id="tenant_acme_corp",
                access_roles=["internal_user", "engineering"],
                classification="internal",
                department="engineering",
                category="documentation",
            )
            new_active_records.append(record)

        else:
            prev_meta = active_records[rel_path]
            if prev_meta["file_hash"] != current_hash:
                new_version = prev_meta["version"] + 1
                v_tag = f"v{new_version}"

                prev_discovered = DiscoveredDocument(
                    relative_path=prev_meta["relative_path"],
                    file_name=prev_meta["file_name"],
                    parent_directory=prev_meta.get("parent_directory", "."),
                    file_extension=prev_meta.get("file_extension", ""),
                    mime_type=prev_meta.get("mime_type", "text/plain"),
                    file_hash=prev_meta["file_hash"],
                    size_bytes=prev_meta["size_bytes"],
                    modified_at=prev_meta["modified_at"],
                    source=SourceType(prev_meta["source"]),
                )

                roles = prev_meta.get("access_roles", "public")
                roles_list = roles.split(",") if isinstance(roles, str) else roles

                old_record = DocumentRecord(
                    doc_id=prev_meta["doc_id"],
                    version=prev_meta["version"],
                    version_tag=prev_meta.get(
                        "version_tag", f"v{prev_meta['version']}"
                    ),
                    is_active=False,
                    state=FileState.MODIFIED,
                    discovered_doc=prev_discovered,
                    tenant_id=prev_meta.get("tenant_id", "default_tenant"),
                    access_roles=roles_list,
                    classification=prev_meta.get("classification", "internal"),
                    department=prev_meta.get("department", ""),
                    category=prev_meta.get("category", ""),
                    metadata=prev_meta,
                )
                records_to_deactivate.append(old_record)

                new_record = DocumentRecord(
                    doc_id=f"{rel_path}:{v_tag}",
                    version=new_version,
                    version_tag=v_tag,
                    state=FileState.MODIFIED,
                    discovered_doc=discovered,
                    tenant_id=prev_meta.get("tenant_id", "default_tenant"),
                    access_roles=roles_list,
                    classification=prev_meta.get("classification", "internal"),
                    department=prev_meta.get("department", ""),
                    category=prev_meta.get("category", ""),
                    metadata=prev_meta,
                )
                new_active_records.append(new_record)

    for rel_path, prev_meta in active_records.items():
        if rel_path not in disk_files:
            deleted_discovered = DiscoveredDocument(
                relative_path=prev_meta["relative_path"],
                file_name=prev_meta["file_name"],
                parent_directory=prev_meta.get("parent_directory", "."),
                file_extension=prev_meta.get("file_extension", ""),
                mime_type=prev_meta.get("mime_type", "text/plain"),
                file_hash=prev_meta["file_hash"],
                size_bytes=prev_meta["size_bytes"],
                modified_at=prev_meta["modified_at"],
                source=SourceType(prev_meta["source"]),
            )

            roles = prev_meta.get("access_roles", "public")
            roles_list = roles.split(",") if isinstance(roles, str) else roles

            deleted_record = DocumentRecord(
                doc_id=prev_meta["doc_id"],
                version=prev_meta["version"],
                version_tag=prev_meta.get("version_tag", f"v{prev_meta['version']}"),
                is_active=False,
                state=FileState.DELETED,
                discovered_doc=deleted_discovered,
                tenant_id=prev_meta.get("tenant_id", "default_tenant"),
                access_roles=roles_list,
                classification=prev_meta.get("classification", "internal"),
                department=prev_meta.get("department", ""),
                category=prev_meta.get("category", ""),
                metadata=prev_meta,
            )
            records_to_deactivate.append(deleted_record)

    update_registry(registry_collection, new_active_records + records_to_deactivate)
    return new_active_records, records_to_deactivate


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


# --- Chunking & Storage ---


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph
    if current:
        chunks.append(current)
    return chunks


def load_and_chunk(
    doc_rec: DocumentRecord, config: PipelineConfig, run_id: str
) -> list[Chunk]:
    file_path = config.raw_dir / doc_rec.discovered_doc.relative_path
    text = file_path.read_text(encoding="utf-8")
    raw_chunks = chunk_text(text, config.chunk_size, config.overlap)

    # Extract complete document metadata dictionary for chunk-level injection
    injected_metadata = doc_rec.to_dict()

    return [
        Chunk(
            content=part,
            run_id=run_id,
            doc_id=doc_rec.doc_id,
            index=index,
            doc_metadata=injected_metadata,
        )
        for index, part in enumerate(raw_chunks)
    ]


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


# --- Pipeline Orchestrator ---


def run_pipeline(
    config: PipelineConfig,
    embedder: Embedder | None = None,
) -> tuple[PipelineRun, list[Chunk]]:
    run = PipelineRun(source=config.source)
    start_time = time.perf_counter()
    chunks: list[Chunk] = []

    if config.recreate and config.persist_dir.exists():
        shutil.rmtree(config.persist_dir)

    client = chromadb.PersistentClient(path=str(config.persist_dir))

    try:
        new_active, deactivated = resolve_file_lifecycles(config, client)

        run.files_new = sum(1 for r in new_active if r.state == FileState.NEW)
        run.files_modified = sum(1 for r in new_active if r.state == FileState.MODIFIED)
        run.files_deleted = sum(1 for r in deactivated if r.state == FileState.DELETED)

        deactivate_old_vector_chunks(client, config.collection_name, deactivated)

        for doc_rec in new_active:
            chunks.extend(load_and_chunk(doc_rec, config, run.run_id))

        run.chunks_created = len(chunks)
        store_chunks(
            chunks, embedder or ChromaEmbedder(), client, config.collection_name
        )
        run.status = RunStatus.SUCCESS

    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error_message = str(exc)
        logger.exception("Pipeline failed")
        raise

    finally:
        run.completed_at = datetime.now(UTC)
        run.duration_seconds = round(time.perf_counter() - start_time, 3)
        log_pipeline_run(client, run, config.runs_collection_name)
        client.close()

    return run, chunks


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Ingest documents with tenant metadata"
    )
    parser.add_argument("--source", type=SourceType, default=SourceType.FILESYSTEM)
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_dir)
    parser.add_argument("--persist-dir", type=Path, default=settings.persist_dir)
    parser.add_argument("--collection-name", type=str, default=settings.collection_name)
    parser.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    parser.add_argument("--overlap", type=int, default=settings.overlap)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    config = PipelineConfig(
        source=args.source,
        raw_dir=args.raw_dir,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        recreate=args.recreate,
    )

    run, chunks = run_pipeline(config)
    logger.info(
        "Run %s complete | Total Chunks Ingested: %d",
        run.run_id,
        len(chunks),
    )


if __name__ == "__main__":
    main()
