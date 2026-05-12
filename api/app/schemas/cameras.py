from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    rtsp_url: str = Field(min_length=10, max_length=1024)
    device_id: UUID
    enabled: bool = False
    consent_attested: bool = False


class CameraUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    enabled: bool | None = None
    consent_attested: bool = False


class CameraOut(BaseModel):
    id: UUID
    device_id: UUID
    name: str
    enabled: bool
    online: bool
    last_frame_at: datetime | None
    consent_attested_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
