from httpx import AsyncClient

from app.security.jwt_self import issue_token, verify_token


def test_jwt_issue_and_verify_roundtrip() -> None:
    from uuid import uuid4

    user_id = uuid4()
    token = issue_token(user_id, "x@y.z")
    claims = verify_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["email"] == "x@y.z"
    assert claims["iss"] == "cams-erp"


async def test_signup_login_me_flow(anon_client: AsyncClient, monkeypatch) -> None:
    # Disable the dev bypass so the auth path is real
    monkeypatch.setenv("CAMS_AUTH_BYPASS", "0")
    from app.config import get_settings

    get_settings.cache_clear()

    r = await anon_client.post(
        "/auth/signup",
        json={"email": "alice@example.com", "password": "supersafe123", "name": "Alice"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "alice@example.com"
    token = body["access_token"]
    assert token

    # Same email again → 409
    dup = await anon_client.post(
        "/auth/signup", json={"email": "Alice@example.com", "password": "anotherone111"}
    )
    assert dup.status_code == 409

    # Login w/ wrong password → 401
    r = await anon_client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "wrong-pass-xx"}
    )
    assert r.status_code == 401

    # Login w/ right password → 200 + token
    r = await anon_client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "supersafe123"}
    )
    assert r.status_code == 200
    token2 = r.json()["access_token"]
    assert token2

    # /auth/me requires bearer
    r = await anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"

    # No bearer → 401
    r = await anon_client.get("/auth/me")
    assert r.status_code == 401


async def test_export_and_delete_me(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/me/export")
    assert r.status_code == 200
    body = r.json()
    assert "user" in body
    assert "cameras" in body
    assert body["user"]["email"]
    assert "password_hash" not in body["user"]

    r = await auth_client.delete("/me")
    assert r.status_code == 204
