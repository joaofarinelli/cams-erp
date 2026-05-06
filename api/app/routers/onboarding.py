"""Camera onboarding endpoints. Discover/probe run on the agent (LAN access)
and the API proxies them via the persistent WS in `app.services.agent_control`.
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.services.agent_control import AgentOfflineError, registry
from app.services.discovery import URL_TEMPLATES, url_templates_for

router = APIRouter(prefix="/onboarding/cameras", tags=["onboarding"])


async def _get_owned_device(db: AsyncSession, user_id: UUID, device_id: UUID) -> Device:
    stmt = select(Device).where(Device.id == device_id, Device.owner_id == user_id)
    device = (await db.execute(stmt)).scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return device


async def _agent_call(device_id: str, type_: str, params: dict, timeout: float) -> dict:
    try:
        return await registry.call(device_id, type_, params, timeout=timeout)
    except AgentOfflineError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "agent_offline") from e
    except asyncio.TimeoutError as e:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "agent_timeout") from e


class DiscoveredDevice(BaseModel):
    ip: str
    name: str | None = None
    vendor: str | None = None
    xaddrs: list[str] = []
    url_templates: list[dict] = []


class DiscoverIn(BaseModel):
    device_id: UUID


class LocalDevice(BaseModel):
    name: str
    kind: str = "video"
    source: str  # ready-to-use source URI, e.g. "dshow:video=Integrated Camera"


class DiscoverOut(BaseModel):
    devices: list[DiscoveredDevice]
    local_devices: list[LocalDevice] = []


@router.post("/discover", response_model=DiscoverOut)
async def discover(
    payload: DiscoverIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoverOut:
    device = await _get_owned_device(db, user.id, payload.device_id)
    resp = await _agent_call(str(device.id), "discover", {"timeout": 3.0}, timeout=15.0)
    if not resp.get("ok"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, resp.get("error", "agent_error"))
    raw = resp.get("result", {}).get("devices", [])
    devices: list[DiscoveredDevice] = []
    for d in raw:
        if not d.get("ip"):
            continue
        devices.append(
            DiscoveredDevice(
                ip=d["ip"],
                name=d.get("name"),
                vendor=d.get("vendor"),
                xaddrs=d.get("xaddrs", []),
                url_templates=d.get("url_templates") or url_templates_for(d.get("vendor")),
            )
        )
    raw_local = resp.get("result", {}).get("local_devices", [])
    locals_ = [
        LocalDevice(name=d["name"], kind=d.get("kind", "video"), source=d["source"])
        for d in raw_local
        if d.get("name") and d.get("source")
    ]
    return DiscoverOut(devices=devices, local_devices=locals_)


class LocalDevicesOut(BaseModel):
    local_devices: list[LocalDevice]


@router.post("/local-devices", response_model=LocalDevicesOut)
async def local_devices(
    payload: DiscoverIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocalDevicesOut:
    """List USB/integrated cameras attached to the PDV machine (Windows DirectShow)."""
    device = await _get_owned_device(db, user.id, payload.device_id)
    resp = await _agent_call(str(device.id), "list_local", {}, timeout=10.0)
    if not resp.get("ok"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, resp.get("error", "agent_error"))
    raw = resp.get("result", {}).get("local_devices", [])
    return LocalDevicesOut(
        local_devices=[
            LocalDevice(name=d["name"], kind=d.get("kind", "video"), source=d["source"])
            for d in raw
            if d.get("name") and d.get("source")
        ]
    )


class ProbeIn(BaseModel):
    device_id: UUID
    rtsp_url: str = Field(min_length=6, max_length=1024)
    include_frame: bool = True


class ProbeOut(BaseModel):
    ok: bool
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    error: str | None = None
    preview_data_url: str | None = None


@router.post("/probe", response_model=ProbeOut)
async def probe(
    payload: ProbeIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProbeOut:
    device = await _get_owned_device(db, user.id, payload.device_id)
    resp = await _agent_call(
        str(device.id),
        "probe",
        {"rtsp_url": payload.rtsp_url, "include_frame": payload.include_frame},
        timeout=20.0,
    )
    if not resp.get("ok"):
        return ProbeOut(ok=False, error=resp.get("error", "agent_error"))
    result = resp.get("result", {})
    return ProbeOut(
        ok=bool(result.get("ok")),
        codec=result.get("codec"),
        width=result.get("width"),
        height=result.get("height"),
        fps=result.get("fps"),
        error=result.get("error"),
        preview_data_url=result.get("preview_data_url"),
    )


class TemplatesOut(BaseModel):
    vendors: dict[str, list[dict]]


@router.get("/templates", response_model=TemplatesOut)
async def templates(user: User = Depends(get_current_user)) -> TemplatesOut:  # noqa: ARG001
    return TemplatesOut(vendors=URL_TEMPLATES)


class AgentStatusOut(BaseModel):
    device_id: UUID
    online: bool


@router.get("/agent-status", response_model=AgentStatusOut)
async def agent_status(
    device_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentStatusOut:
    device = await _get_owned_device(db, user.id, device_id)
    return AgentStatusOut(device_id=device.id, online=registry.is_online(str(device.id)))
