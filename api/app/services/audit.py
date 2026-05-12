from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def record(
    db: AsyncSession,
    *,
    user_id: UUID | None,
    action: str,
    target_type: str,
    target_id: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        ip=ip,
        user_agent=user_agent,
    )
    db.add(entry)
    # caller commits — don't commit here so we stay in the same transaction


async def purge_old_entries(db: AsyncSession) -> int:
    from datetime import timedelta

    from sqlalchemy import delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.commit()
    return result.rowcount
