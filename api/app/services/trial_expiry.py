"""Daily check that flips users whose trial ended to `trial_expired`.

Runs at the same digest hour (default 08:00 America/Sao_Paulo) so existing
infra (timezone helpers, scheduler loop pattern) is reused. Trial expired
users keep their data but quota-zero blocks new event analysis until they
pick a plan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.db.session import SessionLocal
from app.services.digest import _seconds_until_next  # reuse hour-of-day helper


log = logging.getLogger("trial_expiry")


async def _expire_trials_once(db: AsyncSession) -> int:
    now = datetime.now(tz=timezone.utc)
    rows = (
        await db.execute(
            select(User).where(
                User.tier == "trial",
                User.trial_ends_at.is_not(None),
                User.trial_ends_at < now,
            )
        )
    ).scalars().all()
    if not rows:
        return 0
    ids = [u.id for u in rows]
    await db.execute(update(User).where(User.id.in_(ids)).values(tier="trial_expired"))
    await db.commit()
    log.info("expired %s trials", len(ids))
    return len(ids)


async def trial_expiry_scheduler() -> None:
    settings = get_settings()
    while True:
        try:
            wait = _seconds_until_next(settings.digest_hour_local, settings.digest_timezone)
            await asyncio.sleep(wait)
            async with SessionLocal() as db:
                await _expire_trials_once(db)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("trial expiry tick failed: %r", e)
            await asyncio.sleep(60)
