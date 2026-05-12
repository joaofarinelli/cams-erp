import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field

from app.db.models import AgentError, Camera, Device, Rule, User
from app.db.session import SessionLocal, get_db
from app.schemas.agent import AgentConfigOut, CameraConfigItem, HeartbeatIn, HeartbeatOut
from app.security.cognito import get_current_user
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
    device_vals: dict = {"last_heartbeat_at": datetime.now(tz=timezone.utc)}
    if payload.agent_version:
        device_vals["agent_version"] = payload.agent_version
    if payload.self_test is not None:
        device_vals["last_self_test_json"] = payload.self_test
    if payload.tailscale is not None:
        current = (await db.get(Device, device.id)).last_self_test_json or {}
        current["tailscale"] = payload.tailscale
        device_vals["last_self_test_json"] = current
    await db.execute(update(Device).where(Device.id == device.id).values(**device_vals))
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
                face_recognition_enabled=cam.face_recognition_enabled,
                audio_enabled=cam.audio_enabled,
                retention_days=cam.retention_days,
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


class AgentErrorIn(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1024)
    traceback: str | None = Field(default=None, max_length=20000)
    agent_version: str | None = Field(default=None, max_length=32)
    context: dict | None = None


@router.post("/{device_id}/purge", status_code=202)
async def purge_device_clips(
    device_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send purge_clips command to agent. Owner-only."""
    device = (await db.execute(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
    )).scalar_one_or_none()
    if device is None:
        raise HTTPException(404, "Device not found")

    try:
        await registry.send(str(device_id), {"type": "purge_clips"})
    except Exception:  # noqa: BLE001
        pass

    return {"queued": True, "device_id": str(device_id)}


@router.post("/errors", status_code=201)
async def report_error(
    payload: AgentErrorIn,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive a crash/error report from a remote agent.

    Rate-limited to a soft 100/day per device via a quick count check —
    extra rows are dropped silently (returns 202) so a noisy crash loop
    doesn't blow up the table or DB write budget."""
    from datetime import timedelta
    from sqlalchemy import func as sa_func

    since = datetime.now(tz=timezone.utc) - timedelta(days=1)
    count = (
        await db.execute(
            sa_func.count(AgentError.id).select().where(
                AgentError.device_id == device.id, AgentError.occurred_at >= since
            )
        )
    ).scalar() or 0
    if count >= 100:
        return {"ok": True, "dropped": True}
    err = AgentError(
        device_id=device.id,
        kind=payload.kind,
        message=payload.message[:1024],
        traceback=payload.traceback,
        agent_version=payload.agent_version,
        context=payload.context,
    )
    db.add(err)
    await db.commit()
    return {"ok": True, "id": str(err.id)}
