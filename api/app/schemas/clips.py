from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClipUploadRequest(BaseModel):
    camera_id: UUID
    started_at: datetime
    duration_ms: int


class ClipUploadResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in_seconds: int
