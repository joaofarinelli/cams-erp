"""B.1 LGPD soft-delete tests."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

os.environ.setdefault("CAMS_ENV", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_db
from app.main import create_app
from app.security.cognito import get_current_user
from app.security.jwt_self import issue_token
from app.services.account_purge import purge_expired_deletions


# ---------------------------------------------------------------------------
# Test 1: DELETE /me returns 202, sets deleted_at, purge_at = +30d
# ---------------------------------------------------------------------------

async def test_soft_delete_returns_202(db_session: AsyncSession, seed_user: User) -> None:
    app = create_app()
    session_local = db_session.info["session_local"]

    async def override_user() -> User:
        return seed_user

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/me")

    assert r.status_code == 202
    body = r.json()
    assert "deleted_at" in body
    assert "purge_at" in body
    assert "message" in body

    # Verify deleted_at is set in DB
    await db_session.refresh(seed_user)
    assert seed_user.deleted_at is not None

    # purge_at should be ~30 days after deleted_at
    deleted_at = datetime.fromisoformat(body["deleted_at"])
    purge_at = datetime.fromisoformat(body["purge_at"])
    delta = purge_at - deleted_at
    assert 29 <= delta.days <= 30


# ---------------------------------------------------------------------------
# Test 2: After soft-delete, authenticated requests return 410
# ---------------------------------------------------------------------------

async def test_deleted_user_gets_410(db_session: AsyncSession, seed_user: User, monkeypatch) -> None:
    monkeypatch.setenv("CAMS_AUTH_BYPASS", "0")
    from app.config import get_settings
    get_settings.cache_clear()

    # Soft-delete the user in DB
    seed_user.deleted_at = datetime.now(timezone.utc)
    db_session.add(seed_user)
    await db_session.commit()
    await db_session.refresh(seed_user)

    token = issue_token(seed_user.id, seed_user.email)

    app = create_app()
    session_local = db_session.info["session_local"]

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/me/export", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 410
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 3: POST /me/restore within grace period clears deleted_at
# ---------------------------------------------------------------------------

async def test_restore_within_grace_period(db_session: AsyncSession, seed_user: User, monkeypatch) -> None:
    monkeypatch.setenv("CAMS_AUTH_BYPASS", "0")
    from app.config import get_settings
    get_settings.cache_clear()

    # Soft-delete 5 days ago (within 30d grace)
    seed_user.deleted_at = datetime.now(timezone.utc) - timedelta(days=5)
    seed_user.deletion_reason = "test reason"
    db_session.add(seed_user)
    await db_session.commit()
    await db_session.refresh(seed_user)

    token = issue_token(seed_user.id, seed_user.email)

    app = create_app()
    session_local = db_session.info["session_local"]

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/me/restore", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    assert r.json()["restored"] is True

    # Verify deleted_at cleared in DB
    await db_session.refresh(seed_user)
    assert seed_user.deleted_at is None
    assert seed_user.deletion_reason is None

    # User can authenticate again
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r2 = await client.get("/me/export", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 202  # export returns 202 (async) since B.2

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 4: purge_expired_deletions — 31d old user deleted, 15d old stays
# ---------------------------------------------------------------------------

async def test_purge_expired_deletions(db_session: AsyncSession) -> None:
    session_local = db_session.info["session_local"]

    # Create two users: one expired (31d ago), one within grace (15d ago)
    async with session_local() as session:
        old_user = User(
            email=f"old-{uuid4()}@test.com",
            deleted_at=datetime.now(timezone.utc) - timedelta(days=31),
        )
        recent_user = User(
            email=f"recent-{uuid4()}@test.com",
            deleted_at=datetime.now(timezone.utc) - timedelta(days=15),
        )
        session.add(old_user)
        session.add(recent_user)
        await session.commit()
        old_id = old_user.id
        recent_id = recent_user.id

    # Monkey-patch SessionLocal in account_purge to use test session
    import app.services.account_purge as purge_module
    original_session_local = purge_module.SessionLocal
    purge_module.SessionLocal = session_local

    try:
        count = await purge_expired_deletions()
    finally:
        purge_module.SessionLocal = original_session_local

    assert count == 1

    # Verify: old user gone, recent user still exists
    async with session_local() as session:
        gone = (await session.execute(select(User).where(User.id == old_id))).scalar_one_or_none()
        still_there = (await session.execute(select(User).where(User.id == recent_id))).scalar_one_or_none()

    assert gone is None
    assert still_there is not None
