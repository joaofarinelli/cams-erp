"""Usage + tier-status endpoints.

`GET /usage/me` — what the panel reads to render `BillingPage` and the
global `UsageBar` quota widget.

`POST /usage/_internal/increment` — the inference worker calls this with
X-Internal-Token after each VLM call to keep token + cascade counters
accurate (events_count is already incremented in the events router).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import UsageMonthly, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.services.quotas import TIER_LIMITS
from app.services.usage import increment_usage


router = APIRouter(prefix="/usage", tags=["usage"])


class UsageOut(BaseModel):
    month: date
    tier: str
    trial_ends_at: datetime | None
    events_count: int
    vlm_calls: int
    vlm_cascade_calls: int
    vlm_tokens_in: int
    vlm_tokens_out: int
    alerts_count: int
    storage_gb_hours: float
    events_limit: int | None
    cameras_limit: int | None
    events_percent: float
    intensities_allowed: list[str]
    cascade_allowed: bool


def _first_of_month() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


@router.get("/me", response_model=UsageOut)
async def usage_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageOut:
    row = (
        await db.execute(
            select(UsageMonthly).where(
                UsageMonthly.owner_id == user.id,
                UsageMonthly.month == _first_of_month(),
            )
        )
    ).scalar_one_or_none()
    plan = TIER_LIMITS.get(user.tier, TIER_LIMITS["trial"])
    events_limit = plan.get("events_per_month")
    events_count = row.events_count if row else 0
    pct = (events_count / events_limit * 100.0) if (events_limit and events_limit > 0) else 0.0
    return UsageOut(
        month=_first_of_month(),
        tier=user.tier,
        trial_ends_at=user.trial_ends_at,
        events_count=events_count,
        vlm_calls=row.vlm_calls if row else 0,
        vlm_cascade_calls=row.vlm_cascade_calls if row else 0,
        vlm_tokens_in=row.vlm_tokens_in if row else 0,
        vlm_tokens_out=row.vlm_tokens_out if row else 0,
        alerts_count=row.alerts_count if row else 0,
        storage_gb_hours=row.storage_gb_hours if row else 0.0,
        events_limit=events_limit,
        cameras_limit=plan.get("cameras"),
        events_percent=round(pct, 1),
        intensities_allowed=list(plan.get("intensities", [])),
        cascade_allowed=bool(plan.get("cascade", False)),
    )


class IncrementIn(BaseModel):
    owner_id: UUID
    events_count: int = 0
    vlm_calls: int = 0
    vlm_cascade_calls: int = 0
    vlm_tokens_in: int = 0
    vlm_tokens_out: int = 0
    alerts_count: int = 0
    storage_gb_hours: float = 0.0


@router.post("/_internal/increment", status_code=204)
async def usage_increment_internal(
    payload: IncrementIn,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    db: AsyncSession = Depends(get_db),
) -> None:
    settings = get_settings()
    if not settings.internal_token or x_internal_token != settings.internal_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad internal token")
    deltas = payload.model_dump(exclude={"owner_id"})
    await increment_usage(db, payload.owner_id, **deltas)
