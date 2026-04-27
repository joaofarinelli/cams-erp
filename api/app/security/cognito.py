from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db

_jwks_cache: dict[str, Any] | None = None


async def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is None:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(settings.cognito_jwks_url)
            r.raise_for_status()
            _jwks_cache = r.json()
    assert _jwks_cache is not None
    return _jwks_cache


async def verify_cognito_token(token: str) -> dict[str, Any]:
    try:
        jwks = await _fetch_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=None,
            options={"verify_aud": False},
        )
        return claims
    except (JWTError, httpx.HTTPError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


_DEV_SUB = "dev-bypass-sub"
_DEV_EMAIL = "dev@cams-erp.local"


async def _get_or_create_dev_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.cognito_sub == _DEV_SUB))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(cognito_sub=_DEV_SUB, email=_DEV_EMAIL)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> User:
    if get_settings().auth_bypass:
        return await _get_or_create_dev_user(db)

    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    claims = await verify_cognito_token(token)

    result = await db.execute(select(User).where(User.cognito_sub == claims["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(cognito_sub=claims["sub"], email=claims.get("email", ""))
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user
