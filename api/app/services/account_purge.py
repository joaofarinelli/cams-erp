"""Purge soft-deleted users whose grace period has expired (>30 days)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


async def purge_expired_deletions() -> int:
    """Hard-delete users where deleted_at < now() - 30d. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.deleted_at < cutoff)
        )
        users = result.scalars().all()
        for user in users:
            await db.delete(user)
        await db.commit()
        if users:
            logger.info("Purged %d expired accounts", len(users))
        return len(users)


async def account_purge_scheduler() -> None:
    """Run purge daily at 04:00 BRT (07:00 UTC)."""
    import zoneinfo
    tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
    while True:
        now = datetime.now(tz)
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run + timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            await purge_expired_deletions()
        except Exception:
            logger.exception("account_purge_scheduler error")
