import pytest
from fastapi import HTTPException

from app.db.models import Device, User
from app.security.device_auth import (
    generate_device_token,
    hash_device_token,
    verify_device_token,
)


@pytest.mark.asyncio
async def test_generate_and_verify_device_token(db_session) -> None:
    user = User(cognito_sub="abc", email="a@b.com")
    db_session.add(user)
    await db_session.flush()
    device = Device(owner_id=user.id)
    db_session.add(device)
    await db_session.flush()

    raw_token = generate_device_token()
    device.device_token_hash = hash_device_token(raw_token)
    await db_session.commit()

    verified = await verify_device_token(raw_token, db_session)
    assert verified.id == device.id


@pytest.mark.asyncio
async def test_verify_device_token_rejects_unknown(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_device_token("nonexistent-token", db_session)
    assert exc.value.status_code == 401
