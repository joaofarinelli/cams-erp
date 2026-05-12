"""Purge S3 clips older than camera.retention_days. Runs daily 03:00 BRT."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Alert, AuditLog, Camera, Event
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


async def purge_expired_clips(
    session_factory: Callable | None = None,
) -> int:
    """Delete events+S3 objects older than camera.retention_days. Returns count deleted."""
    settings = get_settings()
    factory = session_factory or SessionLocal

    # Try to get S3 client — skip if not configured
    s3 = None
    try:
        kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
        s3 = boto3.client("s3", **kwargs)
    except Exception:
        logger.warning("S3 not available — clip retention will skip S3 deletes")

    total_purged = 0

    async with factory() as db:
        # Fetch all cameras with their retention_days
        cameras = (await db.execute(select(Camera))).scalars().all()

        for camera in cameras:
            retention = camera.retention_days  # int, default 7
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention)

            # Fetch expired events for this camera in batches of 1000
            events = (
                await db.execute(
                    select(Event)
                    .where(Event.camera_id == camera.id, Event.created_at < cutoff)
                    .limit(1000)
                )
            ).scalars().all()

            if not events:
                continue

            event_ids = [e.id for e in events]

            # Delete associated Alerts first (FK RESTRICT on events.id)
            alerts = (
                await db.execute(
                    select(Alert).where(Alert.event_id.in_(event_ids))
                )
            ).scalars().all()
            for alert in alerts:
                await db.delete(alert)

            # Delete S3 objects in batch
            if s3:
                keys = [{"Key": e.s3_key} for e in events if e.s3_key]
                if keys:
                    try:
                        s3.delete_objects(
                            Bucket=settings.clips_bucket,
                            Delete={"Objects": keys},
                        )
                    except ClientError as exc:
                        logger.error(
                            "S3 delete_objects failed for camera %s: %s", camera.id, exc
                        )
                        # Log error but proceed with DB deletion

            # Write audit log entries and delete DB rows
            for event in events:
                db.add(
                    AuditLog(
                        user_id=None,  # system action
                        action="retention_purge",
                        target_type="clip",
                        target_id=event.s3_key or str(event.id),
                        ip=None,
                        user_agent="clip_retention_cron",
                    )
                )
                await db.delete(event)

            await db.commit()
            total_purged += len(events)
            logger.info(
                "Purged %d clips for camera %s (retention=%dd)",
                len(events),
                camera.id,
                retention,
            )

    return total_purged


async def clip_retention_scheduler() -> None:
    """Run daily at 03:00 BRT (06:00 UTC)."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
    while True:
        now = datetime.now(tz)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run + timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            count = await purge_expired_clips()
            logger.info("clip_retention_scheduler: purged %d clips", count)
        except Exception:
            logger.exception("clip_retention_scheduler error")
