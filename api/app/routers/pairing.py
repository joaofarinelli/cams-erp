import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentError, Device, User
from app.db.session import get_db
from app.schemas.pairing import PairCodeOut, PairVerifyIn, PairVerifyOut
from app.security.cognito import get_current_user
from app.security.device_auth import generate_device_token, hash_device_token
from app.services.agent_control import AgentOfflineError, registry

router = APIRouter(prefix="/pair", tags=["pair"])


class DeviceOut(BaseModel):
    id: UUID
    name: str
    paired: bool
    edge_yolo_enabled: bool = False


class DeviceUpdate(BaseModel):
    edge_yolo_enabled: bool | None = None
    name: str | None = None


class DeviceLogs(BaseModel):
    path: str
    content: str
    lines: int


class AgentErrorOut(BaseModel):
    id: UUID
    device_id: UUID
    occurred_at: datetime
    kind: str
    message: str
    traceback: str | None
    agent_version: str | None
    context: dict | None


class DeviceDetail(BaseModel):
    id: UUID
    name: str
    paired: bool
    edge_yolo_enabled: bool
    last_heartbeat_at: datetime | None
    last_self_test_json: dict | None


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


@devices_router.get("/{device_id}/logs", response_model=DeviceLogs)
async def fetch_device_logs(
    device_id: UUID,
    tail: int = 200,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceLogs:
    """Pull the tail of the remote agent's local log via its control WS. Lets
    support debug a customer's PDV without asking them to copy/paste."""
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    try:
        resp = await registry.call(
            str(device.id), "logs", {"tail": tail}, timeout=10.0
        )
    except AgentOfflineError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Agent offline")
    if not resp.get("ok"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, resp.get("error") or "Agent error")
    res = resp.get("result") or {}
    return DeviceLogs(
        path=res.get("path", ""),
        content=res.get("content", ""),
        lines=int(res.get("lines") or 0),
    )


@devices_router.get("/{device_id}", response_model=DeviceDetail)
async def get_device(
    device_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceDetail:
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return DeviceDetail(
        id=device.id,
        name=device.name,
        paired=device.device_token_hash is not None,
        edge_yolo_enabled=device.edge_yolo_enabled,
        last_heartbeat_at=device.last_heartbeat_at,
        last_self_test_json=device.last_self_test_json,
    )


@devices_router.get("/{device_id}/errors", response_model=list[AgentErrorOut])
async def list_device_errors(
    device_id: UUID,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentErrorOut]:
    """Recent crash/error reports submitted by the agent. Newest first."""
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    rows = (
        await db.execute(
            select(AgentError)
            .where(AgentError.device_id == device_id)
            .order_by(AgentError.occurred_at.desc())
            .limit(max(1, min(limit, 500)))
        )
    ).scalars().all()
    return [
        AgentErrorOut(
            id=e.id,
            device_id=e.device_id,
            occurred_at=e.occurred_at,
            kind=e.kind,
            message=e.message,
            traceback=e.traceback,
            agent_version=e.agent_version,
            context=e.context,
        )
        for e in rows
    ]


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
