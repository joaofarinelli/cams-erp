"""Record security incidents and notify affected titulares."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

logger = logging.getLogger(__name__)


async def record_incident(
    db: AsyncSession,
    *,
    description: str,
    affected_user_ids: list[UUID] | None = None,
    affected_all: bool = False,
    severity: str = "medium",
    reported_by: str | None = None,
) -> dict:
    """Log incident. Returns summary dict. Email notification is best-effort."""
    incident = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "description": description,
        "reported_by": reported_by,
        "affected_user_ids": [str(uid) for uid in (affected_user_ids or [])],
        "affected_all": affected_all,
    }
    logger.critical("SECURITY INCIDENT: %s", incident)

    # Notify affected users by email (best-effort; no email service wired yet — log only)
    if affected_all:
        users = (await db.execute(select(User.email, User.name))).all()
    elif affected_user_ids:
        users = (await db.execute(select(User.email, User.name).where(User.id.in_(affected_user_ids)))).all()
    else:
        users = []

    notified = []
    for email, name in users:
        # TODO: wire actual email sending (SES) in production
        logger.info("INCIDENT NOTIFY (email not wired): to=%s", email)
        notified.append(email)

    incident["notified_count"] = len(notified)
    return incident
