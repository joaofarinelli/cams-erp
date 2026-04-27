from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import PresetType

PolygonPoint = tuple[float, float]
Polygon = Annotated[list[PolygonPoint], Field(min_length=3)]


class RuleCreate(BaseModel):
    camera_id: UUID
    preset_type: PresetType
    enabled: bool = True
    zones: dict[str, Polygon]
    sensitivity: int = Field(ge=0, le=100, default=50)
    cooldown_seconds: int = Field(ge=10, le=3600, default=300)


class RuleUpdate(BaseModel):
    enabled: bool | None = None
    zones: dict[str, Polygon] | None = None
    sensitivity: int | None = Field(default=None, ge=0, le=100)
    cooldown_seconds: int | None = Field(default=None, ge=10, le=3600)


class RuleOut(BaseModel):
    id: UUID
    camera_id: UUID
    preset_type: PresetType
    enabled: bool
    zones: dict
    sensitivity: int
    cooldown_seconds: int
    created_at: datetime

    class Config:
        from_attributes = True
