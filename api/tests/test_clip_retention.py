"""Tests for clip_retention purge_expired_clips()."""
from __future__ import annotations

import os

os.environ.setdefault("CAMS_ENV", "test")

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import boto3
import pytest
import pytest_asyncio
from moto import mock_aws
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base
from app.db.models import AuditLog, Camera, Device, Event, User
from app.services.clip_retention import purge_expired_clips


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url.replace("+psycopg", "+asyncpg"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with session_local() as session:
        session.info["session_local"] = session_local
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seed_user(db_session):
    user = User(cognito_sub="ret-test-sub", email="ret@cams-erp.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_device(db_session, seed_user):
    device = Device(owner_id=seed_user.id, name="RetDevice")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    return device


@pytest_asyncio.fixture
async def seed_camera(db_session, seed_device):
    cam = Camera(
        device_id=seed_device.id,
        name="RetCam",
        rtsp_url_encrypted="ZGV2OnRlc3Q=",
        retention_days=7,
    )
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)
    return cam


def make_event(camera_id, s3_key: str, age_days: float) -> Event:
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    return Event(
        camera_id=camera_id,
        s3_key=s3_key,
        motion_score=0.5,
        started_at=created,
        duration_ms=1000,
        created_at=created,
    )


def _factory(db_session):
    return db_session.info["session_local"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_older_than_retention_is_deleted(db_session, seed_camera):
    """Event older than camera.retention_days → deleted from DB + AuditLog created."""
    old_event = make_event(seed_camera.id, "clips/old.mp4", age_days=10)
    db_session.add(old_event)
    await db_session.commit()

    settings = get_settings()

    with mock_aws():
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3.create_bucket(
            Bucket=settings.clips_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )
        s3.put_object(Bucket=settings.clips_bucket, Key="clips/old.mp4", Body=b"data")

        count = await purge_expired_clips(session_factory=_factory(db_session))

    assert count == 1

    session_local = _factory(db_session)
    async with session_local() as s:
        remaining = (await s.execute(select(Event))).scalars().all()
        assert len(remaining) == 0

        audit_logs = (
            await s.execute(
                select(AuditLog).where(AuditLog.action == "retention_purge")
            )
        ).scalars().all()
        assert len(audit_logs) == 1
        assert audit_logs[0].target_id == "clips/old.mp4"
        assert audit_logs[0].user_agent == "clip_retention_cron"
        assert audit_logs[0].user_id is None


@pytest.mark.asyncio
async def test_event_within_retention_not_deleted(db_session, seed_camera):
    """Event within retention period → NOT deleted."""
    fresh_event = make_event(seed_camera.id, "clips/fresh.mp4", age_days=3)
    db_session.add(fresh_event)
    await db_session.commit()

    settings = get_settings()

    with mock_aws():
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3.create_bucket(
            Bucket=settings.clips_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )

        count = await purge_expired_clips(session_factory=_factory(db_session))

    assert count == 0

    session_local = _factory(db_session)
    async with session_local() as s:
        remaining = (await s.execute(select(Event))).scalars().all()
        assert len(remaining) == 1


@pytest.mark.asyncio
async def test_retention_days_per_camera(db_session, seed_device):
    """Camera with retention_days=3: event 4d old deleted, event 2d old stays."""
    cam = Camera(
        device_id=seed_device.id,
        name="ShortRetCam",
        rtsp_url_encrypted="ZGV2OnRlc3Q=",
        retention_days=3,
    )
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)

    old_ev = make_event(cam.id, "clips/4days.mp4", age_days=4)
    fresh_ev = make_event(cam.id, "clips/2days.mp4", age_days=2)
    db_session.add_all([old_ev, fresh_ev])
    await db_session.commit()

    settings = get_settings()

    with mock_aws():
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3.create_bucket(
            Bucket=settings.clips_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )
        s3.put_object(Bucket=settings.clips_bucket, Key="clips/4days.mp4", Body=b"d")

        count = await purge_expired_clips(session_factory=_factory(db_session))

    assert count == 1

    session_local = _factory(db_session)
    async with session_local() as s:
        remaining = (await s.execute(select(Event))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].s3_key == "clips/2days.mp4"


@pytest.mark.asyncio
async def test_s3_unavailable_still_deletes_db_rows(db_session, seed_camera):
    """S3 failure logs warning but does NOT block DB deletion."""
    old_event = make_event(seed_camera.id, "clips/noclip.mp4", age_days=10)
    db_session.add(old_event)
    await db_session.commit()

    with patch("app.services.clip_retention.boto3.client", side_effect=Exception("no s3")):
        count = await purge_expired_clips(session_factory=_factory(db_session))

    assert count == 1

    session_local = _factory(db_session)
    async with session_local() as s:
        remaining = (await s.execute(select(Event))).scalars().all()
        assert len(remaining) == 0

        audit_logs = (
            await s.execute(
                select(AuditLog).where(AuditLog.action == "retention_purge")
            )
        ).scalars().all()
        assert len(audit_logs) == 1
