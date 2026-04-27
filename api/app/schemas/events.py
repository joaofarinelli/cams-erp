from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    camera_id: UUID
    s3_key: str = Field(min_length=10)
    motion_score: float = Field(ge=0, le=1)
    started_at: datetime
    duration_ms: int = Field(ge=1000, le=60_000)


class EventOut(BaseModel):
    id: UUID
    enqueued: bool
