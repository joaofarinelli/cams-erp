"""C.1 LGPD consent log tests."""
from __future__ import annotations

import os

os.environ.setdefault("CAMS_ENV", "test")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConsentLog, User
from app.db.session import get_db
from app.main import create_app
from app.security.cognito import get_current_user


# ---------------------------------------------------------------------------
# Test 1: Signup without terms_accepted → 400
# ---------------------------------------------------------------------------

async def test_signup_without_terms_rejected(anon_client: AsyncClient) -> None:
    r = await anon_client.post(
        "/auth/signup",
        json={
            "email": "noacceptance@example.com",
            "password": "supersafe123",
            "terms_accepted": False,
        },
    )
    assert r.status_code == 400
    assert "termos" in r.json()["detail"].lower() or "aceitar" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 2: Signup with terms_accepted creates 2 ConsentLog rows
# ---------------------------------------------------------------------------

async def test_signup_with_terms_creates_consent_log(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await anon_client.post(
        "/auth/signup",
        json={
            "email": "alice@consent.com",
            "password": "supersafe123",
            "terms_accepted": True,
            "policy_version": "v1.0",
        },
    )
    assert r.status_code == 201

    # Fetch the user
    user = (
        await db_session.execute(select(User).where(User.email == "alice@consent.com"))
    ).scalar_one_or_none()
    assert user is not None
    assert user.policy_version == "v1.0"

    # Expect 2 consent log rows
    logs = (
        await db_session.execute(select(ConsentLog).where(ConsentLog.user_id == user.id))
    ).scalars().all()
    assert len(logs) == 2
    doc_types = {lg.doc_type for lg in logs}
    assert "privacy" in doc_types
    assert "terms" in doc_types
    for lg in logs:
        assert lg.version == "v1.0"


# ---------------------------------------------------------------------------
# Test 3: POST /me/accept-terms creates new ConsentLog rows + updates user
# ---------------------------------------------------------------------------

async def test_accept_terms_endpoint(db_session: AsyncSession, seed_user: User) -> None:
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
        r = await client.post("/me/accept-terms", json={"policy_version": "v1.0"})

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["version"] == "v1.0"

    # Verify DB rows
    logs = (
        await db_session.execute(
            select(ConsentLog).where(ConsentLog.user_id == seed_user.id)
        )
    ).scalars().all()
    assert len(logs) == 2
    doc_types = {lg.doc_type for lg in logs}
    assert doc_types == {"privacy", "terms"}

    # Verify user.policy_version updated
    await db_session.refresh(seed_user)
    assert seed_user.policy_version == "v1.0"


# ---------------------------------------------------------------------------
# Test 4: GET /me/export contains consent_log key
# ---------------------------------------------------------------------------

async def test_export_contains_consent_log(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/me/export")
    assert r.status_code == 200
    body = r.json()
    assert "consent_log" in body
    assert isinstance(body["consent_log"], list)
