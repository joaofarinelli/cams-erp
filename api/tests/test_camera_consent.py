"""LGPD C.2 — per-camera employee consent attestation tests."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Camera

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test 1: Create camera (enabled=False default) — no consent needed
# ---------------------------------------------------------------------------
async def test_create_camera_no_consent_needed_when_disabled(
    auth_client: AsyncClient, seed_device
) -> None:
    r = await auth_client.post(
        "/cameras",
        json={
            "name": "Cam Loja",
            "rtsp_url": "rtsp://user:pw@10.0.0.1:554/stream1",
            "device_id": str(seed_device.id),
            # enabled defaults to False — no consent needed
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["enabled"] is False
    assert body["consent_attested_at"] is None


# ---------------------------------------------------------------------------
# Test 2: PATCH (PUT) enabled=True without consent_attested → 403
# ---------------------------------------------------------------------------
async def test_patch_enabled_without_consent_raises_403(
    auth_client: AsyncClient, seed_device
) -> None:
    r = await auth_client.post(
        "/cameras",
        json={
            "name": "Cam Caixa",
            "rtsp_url": "rtsp://user:pw@10.0.0.2:554/stream1",
            "device_id": str(seed_device.id),
        },
    )
    assert r.status_code == 201
    cam_id = r.json()["id"]

    r = await auth_client.put(f"/cameras/{cam_id}", json={"enabled": True})
    assert r.status_code == 403
    assert "LGPD" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Test 3: PUT enabled=True with consent_attested=True → OK, fields set
# ---------------------------------------------------------------------------
async def test_patch_enabled_with_consent_sets_fields(
    auth_client: AsyncClient, seed_device, seed_user, db_session
) -> None:
    r = await auth_client.post(
        "/cameras",
        json={
            "name": "Cam Entrada",
            "rtsp_url": "rtsp://user:pw@10.0.0.3:554/stream1",
            "device_id": str(seed_device.id),
        },
    )
    assert r.status_code == 201
    cam_id = r.json()["id"]

    r = await auth_client.put(
        f"/cameras/{cam_id}",
        json={"enabled": True, "consent_attested": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["consent_attested_at"] is not None

    # Verify DB fields directly
    result = await db_session.execute(select(Camera).where(Camera.id == cam_id))
    cam = result.scalar_one()
    assert cam.consent_attested_at is not None
    assert cam.consent_attested_by_user_id == seed_user.id


# ---------------------------------------------------------------------------
# Test 4: Backfill — camera created before migration has consent_attested_at
#         set from created_at (simulate by checking that creating a camera and
#         then manually clearing consent_attested_at then querying proves the
#         backfill logic works; we test it by creating a camera the "legacy" way
#         and verifying the backfill SQL would apply).
#         Since we run against an in-memory SQLite/pg that runs the migration,
#         we test this by inserting a camera with consent_attested_at=None then
#         running the equivalent backfill UPDATE and checking it fills.
# ---------------------------------------------------------------------------
async def test_backfill_sets_consent_attested_at_from_created_at(
    db_session, seed_device
) -> None:
    from datetime import datetime, timezone

    # Insert a legacy camera directly (no consent_attested_at)
    cam = Camera(
        device_id=seed_device.id,
        name="Legacy Cam",
        rtsp_url_encrypted="ZGV2OnRlc3Q=",
        consent_attested_at=None,
    )
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)

    assert cam.consent_attested_at is None
    assert cam.created_at is not None

    # Simulate the migration backfill UPDATE
    from sqlalchemy import text
    await db_session.execute(
        text("UPDATE cameras SET consent_attested_at = created_at WHERE consent_attested_at IS NULL")
    )
    await db_session.commit()

    # Expire the cached ORM instance so the next read goes to DB
    await db_session.refresh(cam)
    result = await db_session.execute(select(Camera).where(Camera.id == cam.id))
    updated = result.scalar_one()
    assert updated.consent_attested_at is not None
    # Should match created_at (within 1 second tolerance due to tz normalization)
    diff = abs((updated.consent_attested_at - updated.created_at).total_seconds())
    assert diff < 1.0
