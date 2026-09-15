"""Document domain models: source/file states and document vector records."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    FILESYSTEM = "filesystem"
    API = "api"
    RDBMS = "rdbms"


class FileState(str, Enum):
    NEW = "new"
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    DELETED = "deleted"


class DiscoveredDocument(BaseModel):
    """Raw document metadata extracted during initial discovery or source ingestion."""

    relative_path: str
    file_name: str
    parent_directory: str
    file_extension: str
    mime_type: str
    file_hash: str
    size_bytes: int
    modified_at: float
    source: SourceType = SourceType.FILESYSTEM
    checksum_algorithm: str = "md5"


class DocumentRecord(BaseModel):
    """Vector document model containing explicit metadata attributes and a unified dict."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    doc_id: str
    version: int = 1
    version_tag: str = "v1"
    is_active: bool = True
    state: FileState
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Explicit Multitenancy & RBAC attributes
    tenant_id: str = Field(default="default_tenant")
    access_roles: list[str] = Field(default_factory=lambda: ["public"])
    classification: str = Field(default="internal")
    department: str = Field(default="")
    category: str = Field(default="")

    # Raw source metadata reference
    discovered_doc: DiscoveredDocument

    # Universal metadata dictionary for arbitrary extra fields or vector payload export
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any, /) -> None:
        """Sync top-level attributes into metadata dict and normalize for ChromaDB."""
        base_meta = self._build_default_metadata()
        # System metadata always reflects the record's own fields; custom extra
        # metadata keys extend the dict without overriding system fields.
        self.metadata = {**self.metadata, **base_meta}

    def _build_default_metadata(self) -> dict[str, Any]:
        """Build ChromaDB-compatible metadata (ensuring scalar values only)."""
        doc = self.discovered_doc

        # Flatten list fields (e.g., access_roles) into comma-separated strings for ChromaDB
        roles_str = (
            ",".join(self.access_roles)
            if isinstance(self.access_roles, list)
            else str(self.access_roles)
        )

        return {
            "doc_id": self.doc_id,
            "version": self.version,
            "version_tag": self.version_tag,
            "is_active": self.is_active,
            "state": self.state.value
            if isinstance(self.state, Enum)
            else str(self.state),
            "created_at": self.created_at,
            # Explicit domain & governance attributes
            "tenant_id": self.tenant_id,
            "access_roles": roles_str,
            "classification": self.classification,
            "department": self.department,
            "category": self.category,
            # File system discovery properties
            "relative_path": doc.relative_path,
            "file_name": doc.file_name,
            "parent_directory": doc.parent_directory,
            "file_extension": doc.file_extension,
            "mime_type": doc.mime_type,
            "file_hash": doc.file_hash,
            "checksum_algorithm": doc.checksum_algorithm,
            "size_bytes": doc.size_bytes,
            "modified_at": doc.modified_at,
            "source": doc.source.value
            if isinstance(doc.source, Enum)
            else str(doc.source),
            # Default descriptive field fallbacks
            "doc_type": self.metadata.get("doc_type", "document"),
            "language": self.metadata.get("language", "en"),
            "title": self.metadata.get("title", ""),
            "author": self.metadata.get("author", ""),
            "document_summary": self.metadata.get("document_summary", ""),
            "total_pages": self.metadata.get("total_pages", 0),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the flattened metadata dictionary suitable for ChromaDB vector storage."""
        return self.metadata
