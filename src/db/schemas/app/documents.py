"""App schemas for versioned document records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    doc_id: str
    version: int = Field(default=1, ge=1)
    version_tag: str = Field(default="v1")
    is_active: bool = True
    state: str
    tenant_id: str = Field(default="default_tenant")
    access_roles: list[str] = Field(default_factory=lambda: ["public"])
    classification: str = Field(default="internal")
    department: str = Field(default="")
    category: str = Field(default="")

    relative_path: str
    file_name: str
    parent_directory: str
    file_extension: str
    mime_type: str
    file_hash: str
    checksum_algorithm: str = Field(default="md5")
    size_bytes: int
    modified_at: float
    source: str


class DocumentCreate(DocumentBase):
    """Payload for registering a new document version."""


class DocumentRead(DocumentBase):
    """Document record as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime