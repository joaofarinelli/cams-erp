"""Admin endpoints — require internal bearer token (CAMS_INTERNAL_TOKEN)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.services.incident import record_incident

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.internal_token or x_internal_token != settings.internal_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")


class IncidentIn(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    affected_user_ids: list[UUID] = Field(default_factory=list)
    affected_all: bool = False
    reported_by: str | None = None


@router.post("/incident", status_code=201)
async def create_incident(
    payload: IncidentIn,
    _: None = Depends(_require_internal_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await record_incident(
        db,
        description=payload.description,
        affected_user_ids=payload.affected_user_ids or None,
        affected_all=payload.affected_all,
        severity=payload.severity,
        reported_by=payload.reported_by,
    )
