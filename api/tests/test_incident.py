"""E.1 LGPD breach response — POST /admin/incident tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.db.models import User


TOKEN = "test-internal-token"


@pytest.fixture(autouse=True)
def set_internal_token(monkeypatch):
    monkeypatch.setenv("CAMS_INTERNAL_TOKEN", TOKEN)
    # bust lru_cache so settings picks up the env var
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_incident_no_token_returns_403(anon_client: AsyncClient):
    resp = await anon_client.post(
        "/admin/incident",
        json={"description": "Unauthorized access detected in S3 bucket."},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_incident_affected_all_returns_201(db_session, anon_client: AsyncClient):
    # seed two users
    u1 = User(email="alice@test.com", cognito_sub="sub-alice")
    u2 = User(email="bob@test.com", cognito_sub="sub-bob")
    db_session.add_all([u1, u2])
    await db_session.commit()

    resp = await anon_client.post(
        "/admin/incident",
        headers={"x-internal-token": TOKEN},
        json={
            "description": "Vazamento de credenciais detectado no banco de dados.",
            "severity": "critical",
            "affected_all": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["severity"] == "critical"
    assert "recorded_at" in body
    assert body["notified_count"] >= 2


@pytest.mark.asyncio
async def test_incident_specific_user_ids(db_session, anon_client: AsyncClient):
    u = User(email="charlie@test.com", cognito_sub="sub-charlie")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)

    resp = await anon_client.post(
        "/admin/incident",
        headers={"x-internal-token": TOKEN},
        json={
            "description": "Acesso indevido detectado ao painel administrativo.",
            "severity": "high",
            "affected_user_ids": [str(u.id)],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["notified_count"] == 1
    assert str(u.id) in body["affected_user_ids"]
