import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Rule
from app.db.session import get_db
from app.schemas.agent import AgentConfigOut, CameraConfigItem, HeartbeatIn, HeartbeatOut
from app.security.device_auth import get_current_device
from app.services.kms import decrypt

router = APIRouter(prefix="/agent", tags=["agent"])


def _config_etag(items: list[dict]) -> str:
    return hashlib.sha256(json.dumps(items, sort_keys=True, default=str).encode()).hexdigest()[:16]


@router.post("/heartbeat", response_model=HeartbeatOut)
async def heartbeat(
    payload: HeartbeatIn,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> HeartbeatOut:
    device.last_heartbeat_at = datetime.now(tz=timezone.utc)
    cams = (await db.execute(select(Camera).where(Camera.device_id == device.id))).scalars().all()
    for cam in cams:
        cam.online = payload.cameras_status.get(str(cam.id), False)
    await db.commit()
    rules = (
        await db.execute(select(Rule).join(Camera).where(Camera.device_id == device.id))
    ).scalars().all()
    items = [{"camera_id": str(r.camera_id), "rule": str(r.id)} for r in rules]
    return HeartbeatOut(server_time=datetime.now(tz=timezone.utc), config_etag=_config_etag(items))


@router.get("/config", response_model=AgentConfigOut)
async def get_config(
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> AgentConfigOut:
    cams = (await db.execute(select(Camera).where(Camera.device_id == device.id))).scalars().all()
    out: list[CameraConfigItem] = []
    for cam in cams:
        rules = (
            await db.execute(select(Rule).where(Rule.camera_id == cam.id, Rule.enabled.is_(True)))
        ).scalars().all()
        out.append(
            CameraConfigItem(
                camera_id=cam.id,
                name=cam.name,
                rtsp_url=decrypt(cam.rtsp_url_encrypted),
                rules=[
                    {
                        "id": str(r.id),
                        "preset_type": r.preset_type.value,
                        "zones": r.zones,
                        "sensitivity": r.sensitivity,
                        "cooldown_seconds": r.cooldown_seconds,
                        "custom_prompt": r.custom_prompt,
                    }
                    for r in rules
                ],
            )
        )
    items_for_etag = [{"camera_id": str(c.camera_id), "rules": c.rules} for c in out]
    return AgentConfigOut(etag=_config_etag(items_for_etag), cameras=out)
