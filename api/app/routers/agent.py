import base64
import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Rule
from app.db.session import SessionLocal, get_db
from app.schemas.agent import AgentConfigOut, CameraConfigItem, HeartbeatIn, HeartbeatOut
from app.security.device_auth import get_current_device, verify_device_token
from app.services.agent_control import registry
from app.services.kms import decrypt

log = logging.getLogger("agent")

router = APIRouter(prefix="/agent", tags=["agent"])


@router.websocket("/control")
async def agent_control(ws: WebSocket, token: str = Query(...)) -> None:
    """Persistent control channel for the on-prem agent. Inbound messages from
    the API are jobs (discover/probe). The agent posts back results keyed by
    job_id. Auth via device token in query string."""
    async with SessionLocal() as db:
        try:
            device = await verify_device_token(token, db)
        except Exception:  # noqa: BLE001
            await ws.close(code=4401)
            return
    await ws.accept()
    device_id = str(device.id)
    registry.register(device_id, ws)
    log.info("agent control connected device=%s", device_id)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "frame":
                cam_id = msg.get("camera_id")
                data = msg.get("data")
                if cam_id and data:
                    try:
                        jpeg = base64.b64decode(data)
                    except Exception:  # noqa: BLE001
                        continue
                    await registry.broadcast_frame(cam_id, jpeg)
                continue
            job_id = msg.get("job_id")
            if job_id:
                registry.resolve(job_id, msg)
    except WebSocketDisconnect:
        pass
    finally:
        registry.unregister(device_id, ws)
        log.info("agent control disconnected device=%s", device_id)


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
                        "zones": r.zones,
                        "sensitivity": r.sensitivity,
                        "cooldown_seconds": r.cooldown_seconds,
                        "custom_prompt": r.custom_prompt,
                        "schedule": r.schedule,
                    }
                    for r in rules
                ],
            )
        )
    items_for_etag = [{"camera_id": str(c.camera_id), "rules": c.rules} for c in out]
    items_for_etag.append({"edge_yolo": device.edge_yolo_enabled})
    return AgentConfigOut(
        etag=_config_etag(items_for_etag),
        cameras=out,
        edge_yolo_enabled=device.edge_yolo_enabled,
        device_name=device.name,
    )
