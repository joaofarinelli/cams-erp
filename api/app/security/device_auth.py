import hashlib
import secrets

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device
from app.db.session import SessionLocal


def generate_device_token() -> str:
    return secrets.token_urlsafe(32)


def hash_device_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def verify_device_token(token: str, db: AsyncSession) -> Device:
    h = hash_device_token(token)
    result = await db.execute(select(Device).where(Device.device_token_hash == h))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token")
    return device


async def get_current_device(
    x_device_token: str = Header(..., alias="X-Device-Token"),
) -> Device:
    async with SessionLocal() as db:
        return await verify_device_token(x_device_token, db)
