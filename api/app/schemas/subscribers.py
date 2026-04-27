from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import SubscriberKind


class SubscriberCreate(BaseModel):
    kind: SubscriberKind
    target: str = Field(min_length=4, max_length=256)


class SubscriberOut(BaseModel):
    id: UUID
    kind: SubscriberKind
    target: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True
