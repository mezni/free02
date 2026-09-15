"""Discovery stage: scan the filesystem, fingerprint files, and resolve lifecycles."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb

from src.config import settings
from src.domain.models.document import (
    DiscoveredDocument,
    DocumentRecord,
    FileState,
    SourceType,
)

if TYPE_CHECKING:
    from src.ingestion.pipeline import PipelineConfig

INGESTIBLE_SUFFIXES = {".md", ".txt"}


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
        if path.is_file() and path.suffix.lower() in INGESTIBLE_SUFFIXES
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


def _scan_disk(raw_dir: Path) -> dict[str, Path]:
    disk_files: dict[str, Path] = {}
    if not raw_dir.exists():
        return disk_files
    for file_path in sorted(raw_dir.glob("**/*")):
        if file_path.is_file() and file_path.suffix.lower() in INGESTIBLE_SUFFIXES:
            disk_files[str(file_path.relative_to(raw_dir))] = file_path
    return disk_files


def _build_discovered(
    file_path: Path, rel_path: str, config: PipelineConfig
) -> DiscoveredDocument:
    stat = file_path.stat()
    return DiscoveredDocument(
        relative_path=rel_path,
        file_name=file_path.name,
        parent_directory=str(file_path.relative_to(config.raw_dir).parent),
        file_extension=file_path.suffix.lower(),
        mime_type=detect_mime_type(file_path),
        file_hash=compute_file_hash(file_path),
        size_bytes=stat.st_size,
        modified_at=stat.st_mtime,
        source=config.source,
    )


def _build_record(
    config: PipelineConfig,
    discovered: DiscoveredDocument,
    state: FileState,
    prev_meta: dict | None = None,
) -> DocumentRecord:
    if prev_meta is None:
        version, v_tag = 1, "v1"
        tenant_id = config.tenant_id
        roles = list(config.access_roles)
        classification = config.classification
        department = config.department
        category = config.category
    else:
        version = int(prev_meta["version"]) + 1
        v_tag = f"v{version}"
        tenant_id = prev_meta.get("tenant_id", config.tenant_id)
        roles = _split_roles(prev_meta)
        classification = prev_meta.get("classification", config.classification)
        department = prev_meta.get("department", config.department)
        category = prev_meta.get("category", config.category)

    return DocumentRecord(
        doc_id=f"{discovered.relative_path}:{v_tag}",
        version=version,
        version_tag=v_tag,
        state=state,
        discovered_doc=discovered,
        tenant_id=tenant_id,
        access_roles=roles,
        classification=classification,
        department=department,
        category=category,
        metadata=prev_meta or {},
    )


def _discovered_from_meta(prev_meta: dict) -> DiscoveredDocument:
    return DiscoveredDocument(
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


def _split_roles(prev_meta: dict) -> list[str]:
    roles = prev_meta.get("access_roles", "public")
    return roles.split(",") if isinstance(roles, str) else list(roles)


def _record_from_meta(
    prev_meta: dict, config: PipelineConfig, *, state: FileState, is_active: bool
) -> DocumentRecord:
    return DocumentRecord(
        doc_id=prev_meta["doc_id"],
        version=int(prev_meta["version"]),
        version_tag=prev_meta.get("version_tag", f"v{prev_meta['version']}"),
        is_active=is_active,
        state=state,
        discovered_doc=_discovered_from_meta(prev_meta),
        tenant_id=prev_meta.get("tenant_id", config.tenant_id),
        access_roles=_split_roles(prev_meta),
        classification=prev_meta.get("classification", config.classification),
        department=prev_meta.get("department", config.department),
        category=prev_meta.get("category", config.category),
        metadata=prev_meta,
    )


def resolve_file_lifecycles(
    config: PipelineConfig,
    client: chromadb.Client,
) -> tuple[list[DocumentRecord], list[DocumentRecord], list[DocumentRecord]]:
    """Resolve disk files into (new_active, to_deactivate, unchanged) records."""
    active_records = get_active_registry_records(
        client, config.registry_collection_name
    )
    disk_files = _scan_disk(config.raw_dir)

    new_active_records: list[DocumentRecord] = []
    records_to_deactivate: list[DocumentRecord] = []
    unchanged_records: list[DocumentRecord] = []

    for rel_path, file_path in disk_files.items():
        discovered = _build_discovered(file_path, rel_path, config)

        if rel_path not in active_records:
            new_active_records.append(_build_record(config, discovered, FileState.NEW))
            continue

        prev_meta = active_records[rel_path]
        if prev_meta["file_hash"] == discovered.file_hash:
            unchanged_records.append(
                _record_from_meta(
                    prev_meta, config, state=FileState.UNCHANGED, is_active=True
                )
            )
        else:
            records_to_deactivate.append(
                _record_from_meta(
                    prev_meta, config, state=FileState.MODIFIED, is_active=False
                )
            )
            new_active_records.append(
                _build_record(
                    config, discovered, FileState.MODIFIED, prev_meta=prev_meta
                )
            )

    for rel_path, prev_meta in active_records.items():
        if rel_path not in disk_files:
            records_to_deactivate.append(
                _record_from_meta(
                    prev_meta, config, state=FileState.DELETED, is_active=False
                )
            )

    return new_active_records, records_to_deactivate, unchanged_records
