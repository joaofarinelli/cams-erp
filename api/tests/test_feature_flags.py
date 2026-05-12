"""LGPD C.3 — face/audio/retention opt-in feature flag tests per camera."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Camera, ConsentLog

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_cam(auth_client: AsyncClient, device_id: str) -> str:
    r = await auth_client.post(
        "/cameras",
        json={
            "name": "Test Cam",
            "rtsp_url": "rtsp://user:pw@10.0.0.1:554/stream1",
            "device_id": device_id,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Test 1: PATCH face_recognition_enabled=True without face_consent → 403
# ---------------------------------------------------------------------------
async def test_patch_face_recognition_without_consent_raises_403(
    auth_client: AsyncClient, seed_device
) -> None:
    cam_id = await _create_cam(auth_client, str(seed_device.id))
    r = await auth_client.patch(
        f"/cameras/{cam_id}",
        json={"face_recognition_enabled": True},
    )
    assert r.status_code == 403
    assert "face_consent" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Test 2: PATCH face_recognition_enabled=True with face_consent=True → OK
#         ConsentLog row created with doc_type="face_recognition"
# ---------------------------------------------------------------------------
async def test_patch_face_recognition_with_consent_ok(
    auth_client: AsyncClient, seed_device, seed_user, db_session
) -> None:
    cam_id = await _create_cam(auth_client, str(seed_device.id))
    r = await auth_client.patch(
        f"/cameras/{cam_id}",
        json={"face_recognition_enabled": True, "face_consent": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["face_recognition_enabled"] is True

    # Verify ConsentLog row
    result = await db_session.execute(
        select(ConsentLog).where(
            ConsentLog.user_id == seed_user.id,
            ConsentLog.doc_type == "face_recognition",
        )
    )
    log_row = result.scalar_one_or_none()
    assert log_row is not None
    assert log_row.version == "v1.0"


# ---------------------------------------------------------------------------
# Test 3: PATCH audio_enabled=True without audio_consent → 403
# ---------------------------------------------------------------------------
async def test_patch_audio_without_consent_raises_403(
    auth_client: AsyncClient, seed_device
) -> None:
    cam_id = await _create_cam(auth_client, str(seed_device.id))
    r = await auth_client.patch(
        f"/cameras/{cam_id}",
        json={"audio_enabled": True},
    )
    assert r.status_code == 403
    assert "audio_consent" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Test 4: PATCH audio_enabled=True with audio_consent=True → OK
#         ConsentLog row created with doc_type="audio_monitoring"
# ---------------------------------------------------------------------------
async def test_patch_audio_with_consent_ok(
    auth_client: AsyncClient, seed_device, seed_user, db_session
) -> None:
    cam_id = await _create_cam(auth_client, str(seed_device.id))
    r = await auth_client.patch(
        f"/cameras/{cam_id}",
        json={"audio_enabled": True, "audio_consent": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["audio_enabled"] is True

    result = await db_session.execute(
        select(ConsentLog).where(
            ConsentLog.user_id == seed_user.id,
            ConsentLog.doc_type == "audio_monitoring",
        )
    )
    log_row = result.scalar_one_or_none()
    assert log_row is not None
    assert log_row.version == "v1.0"


# ---------------------------------------------------------------------------
# Test 5: PATCH retention_days=14 → OK, camera.retention_days=14
# ---------------------------------------------------------------------------
async def test_patch_retention_days_ok(
    auth_client: AsyncClient, seed_device, db_session
) -> None:
    cam_id = await _create_cam(auth_client, str(seed_device.id))
    r = await auth_client.patch(
        f"/cameras/{cam_id}",
        json={"retention_days": 14},
    )
    assert r.status_code == 200, r.text
    assert r.json()["retention_days"] == 14

    result = await db_session.execute(select(Camera).where(Camera.id == cam_id))
    cam = result.scalar_one()
    assert cam.retention_days == 14


# ---------------------------------------------------------------------------
# Test 6: GET /agent/config returns feature flags in camera config
# ---------------------------------------------------------------------------
async def test_agent_config_returns_feature_flags(
    device_client: AsyncClient, seed_device, db_session
) -> None:
    # Create a camera directly in DB with known flags
    cam = Camera(
        device_id=seed_device.id,
        name="Flag Cam",
        rtsp_url_encrypted="ZGV2OnRlc3Q=",
        face_recognition_enabled=True,
        audio_enabled=False,
        retention_days=30,
    )
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)

    r = await device_client.get("/agent/config")
    assert r.status_code == 200, r.text
    cameras = r.json()["cameras"]
    assert len(cameras) >= 1

    # Find our camera
    cam_cfg = next((c for c in cameras if c["camera_id"] == str(cam.id)), None)
    assert cam_cfg is not None
    assert cam_cfg["face_recognition_enabled"] is True
    assert cam_cfg["audio_enabled"] is False
    assert cam_cfg["retention_days"] == 30
