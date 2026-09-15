"""SQLAlchemy ORM models.

Register every model here so that imports of `src.db.models` populate
`Base.metadata` for Alembic autogenerate.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

# Must match the output dimension of the embedding model (Chroma defaults to 384).
EMBEDDING_DIM = 384


class DocumentRecord(Base):
    """Versioned document registry entry."""

    __tablename__ = "document_records"

    doc_id: Mapped[str] = mapped_column(String(500), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    version_tag: Mapped[str] = mapped_column(String(20), default="v1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant_id: Mapped[str] = mapped_column(String(128), index=True, default="default_tenant")
    access_roles: Mapped[list] = mapped_column(JSONB, default=list)
    classification: Mapped[str] = mapped_column(String(32), default="internal")
    department: Mapped[str] = mapped_column(String(64), default="")
    category: Mapped[str] = mapped_column(String(64), default="")

    relative_path: Mapped[str] = mapped_column(String(500), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    parent_directory: Mapped[str] = mapped_column(String(500), default=".")
    file_extension: Mapped[str] = mapped_column(String(16), default="")
    mime_type: Mapped[str] = mapped_column(String(64), default="text/plain")
    file_hash: Mapped[str] = mapped_column(String(64))
    checksum_algorithm: Mapped[str] = mapped_column(String(16), default="md5")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    modified_at: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32))


class Chunk(Base):
    """Chunk row with its pgvector embedding and denormalized doc filters."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    doc_id: Mapped[str] = mapped_column(String(500), index=True)
    relative_path: Mapped[str] = mapped_column(String(500), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PipelineRun(Base):
    """Pipeline execution record."""

    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    files_new: Mapped[int] = mapped_column(Integer, default=0)
    files_modified: Mapped[int] = mapped_column(Integer, default=0)
    files_deleted: Mapped[int] = mapped_column(Integer, default=0)
    files_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunEvent(Base):
    """Event journal entry attached to a pipeline run."""

    __tablename__ = "run_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


__all__ = ["Base", "Chunk", "DocumentRecord", "PipelineRun", "RunEvent"]