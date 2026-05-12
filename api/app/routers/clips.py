from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, Camera, Device, Event, Rule, User
from app.db.session import get_db
from app.schemas.clips import ClipUploadRequest, ClipUploadResponse
from app.security.cognito import get_current_user
from app.security.device_auth import get_current_device
from app.services import audit
from app.services.agent_control import AgentOfflineError, registry
from app.services.s3 import signed_get_url, signed_put_url

router = APIRouter(prefix="/clips", tags=["clips"])


@router.post("/upload-url", response_model=ClipUploadResponse)
async def get_upload_url(
    payload: ClipUploadRequest,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> ClipUploadResponse:
    result = await db.execute(
        select(Camera).where(Camera.id == payload.camera_id, Camera.device_id == device.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    today = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")
    s3_key = f"clips/{device.id}/{payload.camera_id}/{today}/{uuid4()}.mp4"
    return ClipUploadResponse(
        upload_url=signed_put_url(s3_key),
        s3_key=s3_key,
        expires_in_seconds=600,
    )


@router.get("/signed-url")
async def get_signed_clip_url(
    request: Request,
    key: str = Query(..., min_length=1, max_length=512),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return short-lived presigned GET URL for a clip. Caller must own the
    device that produced the clip (verified via Alert → Rule → Camera → Device)."""
    stmt = (
        select(Device.owner_id)
        .join(Camera, Camera.device_id == Device.id)
        .join(Event, Event.camera_id == Camera.id)
        .join(Alert, Alert.event_id == Event.id)
        .join(Rule, Rule.id == Alert.rule_id)
        .where(Event.s3_key == key)
        .limit(1)
    )
    owner = (await db.execute(stmt)).scalar_one_or_none()
    if owner != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await audit.record(
        db,
        user_id=user.id,
        action="clip.view",
        target_type="clip",
        target_id=key,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return {"url": signed_get_url(key), "expires_in_seconds": 600}


class SeekBackIn(BaseModel):
    alert_id: UUID
    seconds_before: int = Field(default=30, ge=5, le=600)
    seconds_after: int = Field(default=5, ge=0, le=60)


class SeekBackOut(BaseModel):
    s3_key: str
    frame_count: int


@router.post("/seek-back", response_model=SeekBackOut)
async def seek_back(
    payload: SeekBackIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SeekBackOut:
    """Reconstruct a clip from the agent's local 24h ring buffer covering
    [alert_time - seconds_before, alert_time + seconds_after]. Useful when
    the operator wants context around an alert without paying to stream
    every camera 24/7 to S3."""
    stmt = (
        select(Alert, Event, Camera, Device)
        .join(Event, Event.id == Alert.event_id)
        .join(Camera, Camera.id == Event.camera_id)
        .join(Device, Device.id == Camera.device_id)
        .where(Alert.id == payload.alert_id, Device.owner_id == user.id)
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert, event, camera, device = row

    alert_ts = (event.started_at or alert.created_at).timestamp()
    from_ts = alert_ts - payload.seconds_before
    to_ts = alert_ts + payload.seconds_after

    today = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")
    s3_key = f"clips/{device.id}/{camera.id}/{today}/seek-{uuid4()}.mp4"
    upload_url = signed_put_url(s3_key)

    try:
        resp = await registry.call(
            str(device.id),
            "seek_clip",
            {
                "camera_id": str(camera.id),
                "from_ts": from_ts,
                "to_ts": to_ts,
                "upload_url": upload_url,
            },
            timeout=90.0,
        )
    except AgentOfflineError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Agent offline")
    if not resp.get("ok"):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, resp.get("error") or "agent_error"
        )
    return SeekBackOut(
        s3_key=s3_key,
        frame_count=int(resp.get("result", {}).get("frame_count", 0)),
    )
