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


def resolve_file_lifecycles(
    config: PipelineConfig,
    client: chromadb.Client,
) -> tuple[list[DocumentRecord], list[DocumentRecord]]:
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

    return new_active_records, records_to_deactivate
