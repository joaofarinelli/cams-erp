from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models import AlertStatus, PresetType


class AlertOut(BaseModel):
    id: UUID
    rule_id: UUID
    rule_name: str | None = None
    event_id: UUID
    camera_id: UUID
    preset_type: PresetType
    status: AlertStatus
    score: float
    message: str
    s3_key: str
    created_at: datetime

    class Config:
        from_attributes = True
