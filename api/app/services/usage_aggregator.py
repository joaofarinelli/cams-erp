"""Hourly storage-usage aggregator.

For each owner with any clips this month, list the S3 prefix
`clips/{owner_id}/` once an hour, sum bytes, multiply by 1h, and add the
delta to `usage_monthly.storage_gb_hours`. Cheap because S3 ListObjectsV2
is paginated and we only need the size headers, not contents.

In a future iteration this should be replaced by an `events.bytes` column
summed in SQL — but right now we don't store clip byte size anywhere, so
the S3 list is the source of truth.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Iterable

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, User
from app.db.session import SessionLocal
from app.services.usage import increment_usage


log = logging.getLogger("usage_aggregator")
RUN_INTERVAL_S = 3600  # once an hour


def _make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("CAMS_AWS_ENDPOINT_URL"),
        region_name=os.environ.get("CAMS_AWS_REGION", "auto"),
    )


def _bytes_for_owner_prefix(s3, bucket: str, owner_id: str, max_pages: int = 5) -> int:
    total = 0
    token: str | None = None
    pages = 0
    while True:
        kwargs: dict[str, object] = {
            "Bucket": bucket,
            "Prefix": f"clips/{owner_id}/",
            "MaxKeys": 1000,
        }
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            total += int(obj.get("Size") or 0)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
        pages += 1
        if pages >= max_pages:
            break
    return total


async def _aggregate_once(db: AsyncSession) -> None:
    bucket = os.environ.get("CAMS_CLIPS_BUCKET")
    if not bucket:
        return
    s3 = _make_s3_client()
    rows = (await db.execute(select(User.id))).scalars().all()
    hours_since = RUN_INTERVAL_S / 3600.0
    for owner_id in rows:
        try:
            n_bytes = _bytes_for_owner_prefix(s3, bucket, str(owner_id))
        except Exception as e:  # noqa: BLE001
            log.warning("s3 list failed for %s: %r", owner_id, e)
            continue
        if n_bytes == 0:
            continue
        gb_hours = (n_bytes / 1_000_000_000.0) * hours_since
        await increment_usage(db, owner_id, storage_gb_hours=gb_hours)


async def usage_storage_aggregator() -> None:
    """Long-running task spawned from FastAPI lifespan."""
    log.info("usage storage aggregator armed (every %ss)", RUN_INTERVAL_S)
    while True:
        try:
            await asyncio.sleep(RUN_INTERVAL_S)
            async with SessionLocal() as db:
                await _aggregate_once(db)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("aggregator tick failed: %r", e)
            await asyncio.sleep(60)
