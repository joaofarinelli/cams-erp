import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, User
from app.db.session import get_db
from app.schemas.pairing import PairCodeOut, PairVerifyIn, PairVerifyOut
from app.security.cognito import get_current_user
from app.security.device_auth import generate_device_token, hash_device_token

router = APIRouter(prefix="/pair", tags=["pair"])


class DeviceOut(BaseModel):
    id: UUID
    name: str
    paired: bool
    edge_yolo_enabled: bool = False


class DeviceUpdate(BaseModel):
    edge_yolo_enabled: bool | None = None
    name: str | None = None


devices_router = APIRouter(prefix="/devices", tags=["devices"])


@devices_router.get("", response_model=list[DeviceOut])
async def list_devices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceOut]:
    result = await db.execute(select(Device).where(Device.owner_id == user.id))
    return [
        DeviceOut(
            id=d.id,
            name=d.name,
            paired=d.device_token_hash is not None,
            edge_yolo_enabled=d.edge_yolo_enabled,
        )
        for d in result.scalars().all()
    ]


@devices_router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceOut:
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    if payload.edge_yolo_enabled is not None:
        device.edge_yolo_enabled = payload.edge_yolo_enabled
    if payload.name is not None:
        device.name = payload.name
    await db.commit()
    await db.refresh(device)
    return DeviceOut(
        id=device.id,
        name=device.name,
        paired=device.device_token_hash is not None,
        edge_yolo_enabled=device.edge_yolo_enabled,
    )


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
