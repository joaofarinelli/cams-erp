"""Issue + verify our own JWTs. Replaces Cognito for non-AWS deployments.

Tokens are HS256-signed using settings.jwt_secret. Long-lived (30d) by default
so we don't need a refresh-token round trip. When email verification or RBAC
land, embed those claims here."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import jwt
from jose.exceptions import JWTError

from app.config import get_settings

ALGORITHM = "HS256"
DEFAULT_TTL = timedelta(days=30)


def issue_token(user_id: UUID, email: str, ttl: timedelta = DEFAULT_TTL) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "iss": "cams-erp",
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError(str(e)) from e
