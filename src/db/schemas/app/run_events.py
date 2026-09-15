"""App schemas for per-run event journal entries."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunEventBase(BaseModel):
    run_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunEventCreate(RunEventBase):
    """Payload for appending an event to a pipeline run."""


class RunEventRead(RunEventBase):
    """Event entry as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    event_id: int
    created_at: datetime