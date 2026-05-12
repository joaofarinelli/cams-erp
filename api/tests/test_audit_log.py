"""B.3 audit log tests — clip.view, alert.view, alert.feedback."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Alert, AuditLog, Event, Rule


@pytest.fixture
async def seed_alert(db_session, seed_camera):
    rule = Rule(
        camera_id=seed_camera.id,
        zones={"z": [[0, 0], [1, 1], [1, 0]]},
        custom_prompt="Test prompt",
    )
    db_session.add(rule)
    await db_session.flush()

    event = Event(
        camera_id=seed_camera.id,
        s3_key="clips/test-device/test-cam/2026/01/01/test.mp4",
        motion_score=0.5,
        started_at=datetime.now(tz=timezone.utc),
        duration_ms=5000,
    )
    db_session.add(event)
    await db_session.flush()

    alert = Alert(rule_id=rule.id, event_id=event.id, score=0.85, message="Test alert")
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


async def test_clip_view_creates_audit_log(
    auth_client: AsyncClient, seed_alert, db_session
) -> None:
    """GET /clips/signed-url with valid ownership creates an AuditLog row."""
    s3_key = "clips/test-device/test-cam/2026/01/01/test.mp4"
    with patch("app.routers.clips.signed_get_url", return_value="https://s3.example.com/signed"):
        r = await auth_client.get(f"/clips/signed-url?key={s3_key}")
    assert r.status_code == 200

    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "clip.view")
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].target_type == "clip"
    assert logs[0].target_id == s3_key


async def test_alert_view_creates_audit_log(
    auth_client: AsyncClient, seed_alert, db_session
) -> None:
    """GET /alerts/{id} creates an AuditLog row with action alert.view."""
    r = await auth_client.get(f"/alerts/{seed_alert.id}")
    assert r.status_code == 200

    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "alert.view")
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].target_type == "alert"
    assert logs[0].target_id == str(seed_alert.id)


async def test_alert_feedback_creates_audit_log(
    auth_client: AsyncClient, seed_alert, db_session
) -> None:
    """POST /alerts/{id}/feedback creates an AuditLog row with action alert.feedback."""
    r = await auth_client.post(
        f"/alerts/{seed_alert.id}/feedback?is_false_positive=true"
    )
    assert r.status_code == 200

    logs = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "alert.feedback")
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].target_type == "alert"
    assert logs[0].target_id == str(seed_alert.id)
