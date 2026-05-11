from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

PolygonPoint = tuple[float, float]
Polygon = Annotated[list[PolygonPoint], Field(min_length=3)]


class RuleCreate(BaseModel):
    camera_id: UUID
    name: str | None = Field(default=None, max_length=120)
    enabled: bool = True
    zones: dict[str, Polygon] = Field(default_factory=dict)
    sensitivity: int = Field(ge=0, le=100, default=50)
    cooldown_seconds: int = Field(ge=10, le=3600, default=300)
    custom_prompt: str = Field(min_length=10, max_length=4000)
    schedule: dict | None = None
    analysis_intensity: str = Field(default="normal", pattern=r"^(light|normal|strict)$")


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    zones: dict[str, Polygon] | None = None
    sensitivity: int | None = Field(default=None, ge=0, le=100)
    cooldown_seconds: int | None = Field(default=None, ge=10, le=3600)
    custom_prompt: str | None = Field(default=None, min_length=10, max_length=4000)
    schedule: dict | None = None
    analysis_intensity: str | None = Field(default=None, pattern=r"^(light|normal|strict)$")


class RuleOut(BaseModel):
    id: UUID
    camera_id: UUID
    name: str | None = None
    enabled: bool
    zones: dict
    sensitivity: int
    cooldown_seconds: int
    custom_prompt: str
    schedule: dict | None = None
    analysis_intensity: str = "normal"
    created_at: datetime

    class Config:
        from_attributes = True
