from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_db
from app.security.cognito import get_current_user
from app.services.discovery import url_templates_for, ws_discover
from app.services.rtsp_probe import first_frame_jpeg, jpeg_to_data_url, probe_stream

router = APIRouter(prefix="/onboarding/cameras", tags=["onboarding"])


class DiscoveredDevice(BaseModel):
    ip: str
    name: str | None = None
    vendor: str | None = None
    xaddrs: list[str] = []
    url_templates: list[dict] = []


class DiscoverOut(BaseModel):
    devices: list[DiscoveredDevice]


@router.post("/discover", response_model=DiscoverOut)
async def discover(
    user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
) -> DiscoverOut:
    raw = await ws_discover(timeout=3.0)
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
                url_templates=url_templates_for(d.get("vendor")),
            )
        )
    return DiscoverOut(devices=devices)


class ProbeIn(BaseModel):
    rtsp_url: str = Field(min_length=10, max_length=1024)
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
    user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
) -> ProbeOut:
    info = await probe_stream(payload.rtsp_url, timeout=8.0)
    if not info.get("ok"):
        return ProbeOut(ok=False, error=info.get("error"))
    preview = None
    if payload.include_frame:
        jpeg = await first_frame_jpeg(payload.rtsp_url, timeout=8.0)
        if jpeg is not None:
            preview = jpeg_to_data_url(jpeg)
    return ProbeOut(
        ok=True,
        codec=info["codec"],
        width=info["width"],
        height=info["height"],
        fps=info["fps"],
        preview_data_url=preview,
    )


class TemplatesOut(BaseModel):
    vendors: dict[str, list[dict]]


@router.get("/templates", response_model=TemplatesOut)
async def templates(user: User = Depends(get_current_user)) -> TemplatesOut:  # noqa: ARG001
    from app.services.discovery import URL_TEMPLATES

    return TemplatesOut(vendors=URL_TEMPLATES)
