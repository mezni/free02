"""App schemas for pipeline run records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunBase(BaseModel):
    run_id: str
    source: str
    status: str = Field(default="running")
    files_new: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_unchanged: int = 0
    chunks_created: int = 0
    error_message: str | None = None


class PipelineRunCreate(PipelineRunBase):
    """Payload for recording a completed pipeline run."""


class PipelineRunRead(PipelineRunBase):
    """Pipeline run record as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None