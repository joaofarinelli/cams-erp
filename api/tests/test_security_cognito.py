import pytest
from fastapi import HTTPException

from app.security.cognito import verify_cognito_token


@pytest.mark.asyncio
async def test_verify_cognito_token_rejects_garbage() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_cognito_token("not-a-jwt")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_cognito_token_returns_claims_for_valid_token(monkeypatch) -> None:
    fake_jwks = {"keys": [{"kid": "abc", "kty": "RSA", "n": "...", "e": "AQAB"}]}
    fake_claims = {"sub": "user-uuid", "email": "owner@example.com", "token_use": "access"}

    async def fake_get_jwks() -> dict:
        return fake_jwks

    def fake_decode(
        token: str,
        jwks: dict,
        algorithms: list[str],
        audience: str | None = None,
        options: dict | None = None,
    ) -> dict:
        return fake_claims

    import app.security.cognito as cog

    monkeypatch.setattr(cog, "_jwks_cache", None)
    monkeypatch.setattr(cog, "_fetch_jwks", fake_get_jwks)
    monkeypatch.setattr(cog.jwt, "decode", fake_decode)

    claims = await verify_cognito_token("valid.jwt.token")
    assert claims["sub"] == "user-uuid"
