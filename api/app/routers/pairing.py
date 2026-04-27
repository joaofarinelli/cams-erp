import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, User
from app.db.session import get_db
from app.schemas.pairing import PairCodeOut, PairVerifyIn, PairVerifyOut
from app.security.cognito import get_current_user
from app.security.device_auth import generate_device_token, hash_device_token

router = APIRouter(prefix="/pair", tags=["pair"])


@router.post("/code", response_model=PairCodeOut, status_code=201)
async def create_pair_code(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairCodeOut:
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
    device = Device(owner_id=user.id, pair_code=code, pair_code_expires_at=expires)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return PairCodeOut(pair_code=code, expires_at=expires, device_id=device.id)


@router.post("/verify", response_model=PairVerifyOut)
async def verify_pair_code(
    payload: PairVerifyIn,
    db: AsyncSession = Depends(get_db),
) -> PairVerifyOut:
    result = await db.execute(select(Device).where(Device.pair_code == payload.pair_code))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")
    if device.pair_code_expires_at is None or device.pair_code_expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code expired")
    if device.device_token_hash is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already paired")

    raw_token = generate_device_token()
    device.device_token_hash = hash_device_token(raw_token)
    device.pair_code = None
    device.pair_code_expires_at = None
    await db.commit()
    await db.refresh(device)
    return PairVerifyOut(device_id=device.id, device_token=raw_token)
