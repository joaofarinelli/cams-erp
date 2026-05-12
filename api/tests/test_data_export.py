"""Tests for B.2: rate-limited async data export."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.db.models import DataExportRequest, Device
from app.db.session import get_db
from app.main import create_app
from app.security.cognito import get_current_user
from app.services.data_export import build_export_zip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_ctx(seed_user, db_session):
    """Return an AsyncClient context manager with both user+db overrides."""
    app = create_app()
    session_local = db_session.info["session_local"]

    async def override_user():
        return seed_user

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Test 1: First export → 202 + DataExportRequest created
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_export_returns_202(db_session, seed_user):
    with patch("app.routers.privacy.process_export_request", new_callable=AsyncMock):
        async with _make_client_ctx(seed_user, db_session) as client:
            resp = await client.get("/me/export")

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "processing"
    assert "export_id" in body

    # DB record created
    from uuid import UUID
    rec = await db_session.get(DataExportRequest, UUID(body["export_id"]))
    assert rec is not None
    assert rec.user_id == seed_user.id
    assert rec.status == "pending"


# ---------------------------------------------------------------------------
# Test 2: Second export within 1 hour → 429
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_second_export_within_hour_returns_429(db_session, seed_user):
    # Pre-insert a recent export request
    existing = DataExportRequest(user_id=seed_user.id)
    db_session.add(existing)
    await db_session.commit()

    with patch("app.routers.privacy.process_export_request", new_callable=AsyncMock):
        async with _make_client_ctx(seed_user, db_session) as client:
            resp = await client.get("/me/export")

    assert resp.status_code == 429
    assert "Export já solicitado" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 3: After 1 hour → second request succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_after_cooldown_succeeds(db_session, seed_user):
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    stale = DataExportRequest(user_id=seed_user.id)
    db_session.add(stale)
    await db_session.commit()
    await db_session.refresh(stale)

    await db_session.execute(
        update(DataExportRequest).where(DataExportRequest.id == stale.id).values(requested_at=old_time)
    )
    await db_session.commit()

    with patch("app.routers.privacy.process_export_request", new_callable=AsyncMock):
        async with _make_client_ctx(seed_user, db_session) as client:
            resp = await client.get("/me/export")

    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Test 4: build_export_zip produces valid ZIP with data.json + manifest.json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_zip_content(db_session, seed_user):
    device = Device(owner_id=seed_user.id, name="Test Cam")
    db_session.add(device)
    await db_session.commit()

    zip_bytes, sha256_hex = await build_export_zip(seed_user.id, db_session)

    assert len(sha256_hex) == 64
    assert sha256_hex == hashlib.sha256(zip_bytes).hexdigest()

    buf = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        assert "data.json" in names
        assert "manifest.json" in names

        data = json.loads(zf.read("data.json"))
        assert "user" in data
        assert "devices" in data
        assert len(data["devices"]) == 1

        manifest = json.loads(zf.read("manifest.json"))
        assert "sha256_data" in manifest
        assert "exported_at" in manifest

    buf2 = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf2, "r") as zf2:
        raw_data = zf2.read("data.json")
        raw_manifest = json.loads(zf2.read("manifest.json"))
    assert raw_manifest["sha256_data"] == hashlib.sha256(raw_data).hexdigest()
