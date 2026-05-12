"""G.2 — End-to-end LGPD compliance scenarios.

Five scenarios that exercise the full compliance stack via the HTTP API
and service layer, verifying that each LGPD control works together.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db.models import AuditLog, Camera, Device, Event, User
from app.security.jwt_self import issue_token


# ---------------------------------------------------------------------------
# Scenario 1: Signup without terms → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario1_signup_without_terms_rejected(anon_client):
    """POST /auth/signup without terms_accepted=true must return 400."""
    r = await anon_client.post(
        "/auth/signup",
        json={
            "email": "lgpd1@test.com",
            "password": "Password123!",
            "terms_accepted": False,
        },
    )
    assert r.status_code == 400
    assert "termos" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Scenario 2: Face toggle without consent → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario2_face_toggle_without_consent_rejected(
    auth_client, db_session, seed_user
):
    """Enabling face recognition without consent must return 403."""
    # Create device
    device = Device(owner_id=seed_user.id, name="Test PDV")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    # Create camera with LGPD consent already attested (pass the C.2 gate)
    cam = Camera(
        device_id=device.id,
        name="Cam 1",
        rtsp_url_encrypted="ZGV2OnRlc3Q=",
    )
    cam.consent_attested_at = datetime.now(timezone.utc)
    cam.consent_attested_by_user_id = seed_user.id
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)

    # Try to enable face_recognition WITHOUT face_consent
    r = await auth_client.patch(
        f"/cameras/{cam.id}",
        json={
            "face_recognition_enabled": True,
            "face_consent": False,
        },
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Scenario 3: Full delete lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario3_delete_restore_and_purge(
    auth_client, db_session, seed_user, monkeypatch
):
    """Full delete lifecycle: soft-delete → 410 → restore → purge after 31d → user gone."""
    from httpx import ASGITransport, AsyncClient
    from app.db.session import get_db
    from app.main import create_app
    import app.services.account_purge as purge_module

    session_local = db_session.info["session_local"]

    # 1. Soft-delete (auth_client has override_user, delete works fine)
    r = await auth_client.delete("/me")
    assert r.status_code == 202
    body = r.json()
    assert "purge_at" in body

    # Mark deleted_at in DB (already done by endpoint, just refresh)
    await db_session.refresh(seed_user)
    assert seed_user.deleted_at is not None

    # 2. Verify access blocked — use real JWT path so the deletion check runs
    monkeypatch.setenv("CAMS_AUTH_BYPASS", "0")
    from app.config import get_settings
    get_settings.cache_clear()

    token = issue_token(seed_user.id, seed_user.email)

    app_real = create_app()

    async def override_get_db():
        async with session_local() as session:
            yield session

    app_real.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app_real), base_url="http://test"
    ) as real_client:
        r = await real_client.get("/cameras", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 410

        # 3. Restore via self-issued token
        r = await real_client.post(
            "/me/restore", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        assert r.json()["restored"] is True

        # 4. Access restored
        r = await real_client.get("/cameras", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    get_settings.cache_clear()

    # 5. Soft-delete again, backdate 31 days, then purge → user gone
    await db_session.refresh(seed_user)
    seed_user.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
    await db_session.commit()

    original_session_local = purge_module.SessionLocal
    purge_module.SessionLocal = session_local
    try:
        deleted_count = await purge_module.purge_expired_deletions()
    finally:
        purge_module.SessionLocal = original_session_local

    assert deleted_count >= 1

    # User gone from DB
    result = await db_session.execute(
        select(User).where(User.id == seed_user.id)
    )
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Scenario 4: GET /me/export contains all required sections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario4_export_contains_all_required_sections(
    auth_client, db_session, seed_user
):
    """Data export must contain user, devices, cameras, rules, alerts, audit_log, consent_log."""
    # Hit the endpoint (background task suppressed so it doesn't race)
    with patch(
        "app.routers.privacy.process_export_request", new_callable=AsyncMock
    ):
        r = await auth_client.get("/me/export")

    assert r.status_code == 202
    body = r.json()
    assert "export_id" in body
    assert body["status"] == "processing"

    # Verify zip content directly via service
    from app.services.data_export import build_export_zip

    zip_bytes, sha256 = await build_export_zip(seed_user.id, db_session)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        data = json.loads(zf.read("data.json"))
        manifest = json.loads(zf.read("manifest.json"))

    for section in ("user", "devices", "cameras", "rules", "alerts", "audit_log", "consent_log"):
        assert section in data, f"Missing section: {section}"

    assert "sha256_data" in manifest
    assert len(sha256) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Scenario 5: Clip beyond retention → cron deletes + audit log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario5_clip_retention_purge(db_session, seed_user):
    """Clips older than camera.retention_days are deleted; recent ones survive; audit log written."""
    from app.services.clip_retention import purge_expired_clips
    from unittest.mock import patch

    # Create device + camera with retention_days=7
    device = Device(owner_id=seed_user.id, name="Retention Test PDV")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    cam = Camera(
        device_id=device.id,
        name="Retention Cam",
        rtsp_url_encrypted="ZGV2OnRlc3Q=",
        retention_days=7,
    )
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)

    # Create old (9d) and recent (3d) events
    def _make_event(camera_id, s3_key: str, age_days: float) -> Event:
        created = datetime.now(timezone.utc) - timedelta(days=age_days)
        return Event(
            camera_id=camera_id,
            s3_key=s3_key,
            motion_score=0.5,
            started_at=created,
            duration_ms=1000,
            created_at=created,
        )

    old_event = _make_event(cam.id, "clips/test/old.mp4", 9)
    recent_event = _make_event(cam.id, "clips/test/recent.mp4", 3)
    db_session.add_all([old_event, recent_event])
    await db_session.commit()

    session_factory = db_session.info["session_local"]

    # Suppress real S3 calls
    with patch("app.services.clip_retention.boto3.client", side_effect=Exception("no s3")):
        deleted = await purge_expired_clips(session_factory=session_factory)

    assert deleted >= 1

    # Clear stale cache and verify DB state
    await db_session.rollback()

    old_check = (
        await db_session.execute(select(Event).where(Event.id == old_event.id))
    ).scalar_one_or_none()
    assert old_check is None, "Old event should be purged"

    recent_check = (
        await db_session.execute(select(Event).where(Event.id == recent_event.id))
    ).scalar_one_or_none()
    assert recent_check is not None, "Recent event should survive"

    # AuditLog entry created for the purged clip
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "retention_purge",
                AuditLog.target_id == old_event.s3_key,
            )
        )
    ).scalar_one_or_none()
    assert audit is not None, "AuditLog entry missing for purged clip"
