"""D.2 LGPD — remote ring-buffer purge tests."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("CAMS_ENV", "test")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, User
from app.db.session import get_db
from app.main import create_app
from app.security.cognito import get_current_user


# ---------------------------------------------------------------------------
# Test 1: owner hits POST /agent/{device_id}/purge → 202
# ---------------------------------------------------------------------------

async def test_purge_owner_returns_202(
    db_session: AsyncSession,
    seed_user: User,
    seed_device: Device,
) -> None:
    app = create_app()
    session_local = db_session.info["session_local"]

    async def override_user() -> User:
        return seed_user

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_get_db

    with patch("app.services.agent_control.registry.send", new_callable=AsyncMock) as mock_send:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(f"/agent/{seed_device.id}/purge")

    assert r.status_code == 202
    body = r.json()
    assert body["queued"] is True
    assert body["device_id"] == str(seed_device.id)
    mock_send.assert_awaited_once_with(str(seed_device.id), {"type": "purge_clips"})


# ---------------------------------------------------------------------------
# Test 2: non-owner device → 404
# ---------------------------------------------------------------------------

async def test_purge_non_owner_returns_404(
    db_session: AsyncSession,
    seed_device: Device,
) -> None:
    """A different user trying to purge another user's device gets 404."""
    app = create_app()
    session_local = db_session.info["session_local"]

    # Create a second user (not the owner)
    other_user = User(cognito_sub="other-sub", email="other@cams-erp.com")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    async def override_user() -> User:
        return other_user

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(f"/agent/{seed_device.id}/purge")

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Test 3: DELETE /me sends purge_clips to all owner devices
# ---------------------------------------------------------------------------

async def test_delete_me_sends_purge_to_devices(
    db_session: AsyncSession,
    seed_user: User,
    seed_device: Device,
) -> None:
    app = create_app()
    session_local = db_session.info["session_local"]

    async def override_user() -> User:
        return seed_user

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_get_db

    with patch("app.services.agent_control.registry.send", new_callable=AsyncMock) as mock_send:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete("/me")

    assert r.status_code == 202
    # registry.send must have been called for the device
    mock_send.assert_awaited_once_with(str(seed_device.id), {"type": "purge_clips"})
