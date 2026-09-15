"""App schemas for document chunks."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkBase(BaseModel):
    content: str
    run_id: str
    doc_id: str
    chunk_index: int
    embedding: list[float] = Field(default_factory=list)

    doc_metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkCreate(ChunkBase):
    """Payload for storing a chunk with its embedding."""


class ChunkRead(ChunkBase):
    """Chunk record as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime