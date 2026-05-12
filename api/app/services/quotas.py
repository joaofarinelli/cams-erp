"""Tier-based quotas + check_quota helper.

`TIER_LIMITS` is the source of truth for what each plan can do. Values
are intentionally generous on the free `trial` so new accounts can play
without hitting walls in the first hour, but tight enough that abandoned
accounts don't burn LLM budget forever.

`check_quota(owner_id, kind)` returns (allowed, current, limit) so the
caller can decide between soft-skip (still record event, mark
`analysis_skipped`) and hard-reject (HTTP 429). Soft window is 110% —
gives 10% buffer before bouncing.

`None` limit means unlimited (enterprise).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageMonthly, User


TIER_LIMITS: dict[str, dict[str, Any]] = {
    "trial": {
        "cameras": 2,
        "events_per_month": 100,
        "intensities": ["light", "normal"],
        "cascade": False,
    },
    "starter": {
        "cameras": 4,
        "events_per_month": 1200,
        "intensities": ["light", "normal"],
        "cascade": False,
    },
    "pro": {
        "cameras": 20,
        "events_per_month": 30000,
        "intensities": ["light", "normal", "strict"],
        "cascade": True,
    },
    "business": {
        "cameras": 50,
        "events_per_month": 100000,
        "intensities": ["light", "normal", "strict"],
        "cascade": True,
    },
    "enterprise": {
        "cameras": None,
        "events_per_month": None,
        "intensities": ["light", "normal", "strict"],
        "cascade": True,
    },
    "trial_expired": {
        "cameras": 0,
        "events_per_month": 0,
        "intensities": [],
        "cascade": False,
    },
}


SOFT_LIMIT_FACTOR = 1.10  # accept up to 110% before rejecting


def _first_of_month() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


async def get_user_tier(db: AsyncSession, owner_id: UUID) -> str:
    user = (
        await db.execute(select(User.tier).where(User.id == owner_id))
    ).scalar_one_or_none()
    return user or "trial"


async def check_quota(
    db: AsyncSession,
    owner_id: UUID,
    kind: str = "events_per_month",
) -> tuple[bool, int, int | None]:
    """Returns (allowed:bool, current:int, limit:int|None).

    `allowed` is False only when the hard limit (110% of plan) is exceeded;
    callers should still soft-accept between 100% and 110%."""
    tier = await get_user_tier(db, owner_id)
    plan = TIER_LIMITS.get(tier, TIER_LIMITS["trial"])
    limit = plan.get(kind)
    if limit is None:
        # Unlimited — only fetch current for display.
        row = (
            await db.execute(
                select(UsageMonthly).where(
                    UsageMonthly.owner_id == owner_id,
                    UsageMonthly.month == _first_of_month(),
                )
            )
        ).scalar_one_or_none()
        current = getattr(row, kind.replace("_per_month", "_count"), 0) if row else 0
        return True, current, None

    row = (
        await db.execute(
            select(UsageMonthly).where(
                UsageMonthly.owner_id == owner_id,
                UsageMonthly.month == _first_of_month(),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return True, 0, int(limit)

    if kind == "events_per_month":
        current = row.events_count
    else:
        current = int(getattr(row, kind, 0))
    allowed = current < int(limit * SOFT_LIMIT_FACTOR)
    return allowed, current, int(limit)


def tier_allows_intensity(tier: str, intensity: str) -> bool:
    plan = TIER_LIMITS.get(tier, TIER_LIMITS["trial"])
    return intensity in plan.get("intensities", [])


def tier_allows_cascade(tier: str) -> bool:
    plan = TIER_LIMITS.get(tier, TIER_LIMITS["trial"])
    return bool(plan.get("cascade", False))
