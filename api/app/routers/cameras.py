import asyncio
import base64
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field

from app.db.models import Camera, ConsentLog, Device, User
from app.db.session import SessionLocal, get_db
from app.schemas.cameras import CameraCreate, CameraOut, CameraUpdate
from app.security.cognito import get_current_user
from app.security.jwt_self import verify_token
from app.services.agent_control import AgentOfflineError, registry
from app.services.kms import decrypt, encrypt

router = APIRouter(prefix="/cameras", tags=["cameras"])


async def _owned_camera(camera_id: UUID, user: User, db: AsyncSession) -> Camera:
    result = await db.execute(
        select(Camera).join(Device).where(Camera.id == camera_id, Device.owner_id == user.id)
    )
    cam = result.scalar_one_or_none()
    if cam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return cam


class BulkCameraItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    rtsp_url: str = Field(min_length=1)


class BulkCameraCreate(BaseModel):
    device_id: UUID
    cameras: list[BulkCameraItem] = Field(min_length=1, max_length=64)


@router.post("/bulk", response_model=list[CameraOut], status_code=201)
async def create_cameras_bulk(
    payload: BulkCameraCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Camera]:
    """Create N cameras at once for the same device. Used by the wizard after
    ONVIF discovery + bulk credential probe finds working URLs for each
    camera in one go, so the customer doesn't paste user/senha N times."""
    result = await db.execute(
        select(Device).where(Device.id == payload.device_id, Device.owner_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    created: list[Camera] = []
    for item in payload.cameras:
        cam = Camera(
            device_id=device.id,
            name=item.name,
            rtsp_url_encrypted=encrypt(item.rtsp_url),
        )
        db.add(cam)
        created.append(cam)
    await db.commit()
    for cam in created:
        await db.refresh(cam)
    return created


_LGPD_CONSENT_MSG = (
    "Câmera não pode ser ativada sem atestado de afixação do aviso de monitoramento LGPD. "
    "Envie consent_attested=true."
)


@router.post("", response_model=CameraOut, status_code=201)
async def create_camera(
    payload: CameraCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    result = await db.execute(
        select(Device).where(Device.id == payload.device_id, Device.owner_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")

    if payload.enabled and not payload.consent_attested:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _LGPD_CONSENT_MSG)

    cam = Camera(
        device_id=device.id,
        name=payload.name,
        rtsp_url_encrypted=encrypt(payload.rtsp_url),
        enabled=payload.enabled,
    )
    if payload.consent_attested:
        cam.consent_attested_at = datetime.now(timezone.utc)
        cam.consent_attested_by_user_id = user.id
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    return cam


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Camera]:
    result = await db.execute(
        select(Camera).join(Device).where(Device.owner_id == user.id)
    )
    return list(result.scalars().all())


_FACE_CONSENT_MSG = (
    "Reconhecimento facial requer consentimento explícito. Envie face_consent=true."
)
_AUDIO_CONSENT_MSG = (
    "Monitoramento de áudio requer consentimento explícito. Envie audio_consent=true."
)


async def _apply_feature_flags(
    cam: Camera,
    payload: CameraUpdate,
    user: User,
    request: Request,
    db: AsyncSession,
) -> None:
    """Apply face/audio/retention toggles and record ConsentLog entries as required."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    if payload.face_recognition_enabled is True:
        if not payload.face_consent:
            raise HTTPException(status.HTTP_403_FORBIDDEN, _FACE_CONSENT_MSG)
        db.add(
            ConsentLog(
                user_id=user.id,
                doc_type="face_recognition",
                version="v1.0",
                ip=ip,
                user_agent=ua,
            )
        )
        cam.face_recognition_enabled = True
    elif payload.face_recognition_enabled is False:
        cam.face_recognition_enabled = False

    if payload.audio_enabled is True:
        if not payload.audio_consent:
            raise HTTPException(status.HTTP_403_FORBIDDEN, _AUDIO_CONSENT_MSG)
        db.add(
            ConsentLog(
                user_id=user.id,
                doc_type="audio_monitoring",
                version="v1.0",
                ip=ip,
                user_agent=ua,
            )
        )
        cam.audio_enabled = True
    elif payload.audio_enabled is False:
        cam.audio_enabled = False

    if payload.retention_days is not None:
        cam.retention_days = payload.retention_days


@router.put("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    cam = await _owned_camera(camera_id, user, db)
    if payload.name is not None:
        cam.name = payload.name
    if payload.rtsp_url is not None:
        cam.rtsp_url_encrypted = encrypt(payload.rtsp_url)
    if payload.enabled is True:
        # Consent required: either already attested or attested in this request
        if cam.consent_attested_at is None and not payload.consent_attested:
            raise HTTPException(status.HTTP_403_FORBIDDEN, _LGPD_CONSENT_MSG)
        cam.enabled = True
    elif payload.enabled is False:
        cam.enabled = False
    if payload.consent_attested:
        cam.consent_attested_at = datetime.now(timezone.utc)
        cam.consent_attested_by_user_id = user.id
    await _apply_feature_flags(cam, payload, user, request, db)
    await db.commit()
    await db.refresh(cam)
    return cam


@router.patch("/{camera_id}", response_model=CameraOut)
async def patch_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Partial update — delegates to same logic as PUT."""
    cam = await _owned_camera(camera_id, user, db)
    if payload.name is not None:
        cam.name = payload.name
    if payload.rtsp_url is not None:
        cam.rtsp_url_encrypted = encrypt(payload.rtsp_url)
    if payload.enabled is True:
        if cam.consent_attested_at is None and not payload.consent_attested:
            raise HTTPException(status.HTTP_403_FORBIDDEN, _LGPD_CONSENT_MSG)
        cam.enabled = True
    elif payload.enabled is False:
        cam.enabled = False
    if payload.consent_attested:
        cam.consent_attested_at = datetime.now(timezone.utc)
        cam.consent_attested_by_user_id = user.id
    await _apply_feature_flags(cam, payload, user, request, db)
    await db.commit()
    await db.refresh(cam)
    return cam


@router.get("/{camera_id}/thumb.jpg")
async def camera_thumbnail(
    camera_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a JPEG snapshot of the camera. Asks the on-prem agent to grab
    a single frame via RTSP — no dependency on a recorded clip.

    Auth: JWT in the `?token=` query string (since <img> tags can't send
    Authorization headers).
    """
    try:
        user_id = verify_token(token)["sub"]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from e

    stmt = (
        select(Camera, Device)
        .join(Device, Camera.device_id == Device.id)
        .where(Camera.id == camera_id, Device.owner_id == user_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    cam, device = row
    rtsp_url = decrypt(cam.rtsp_url_encrypted)
    device_id = str(device.id)

    if not registry.is_online(device_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "agent_offline")
    try:
        resp = await registry.call(device_id, "snapshot", {"rtsp_url": rtsp_url}, timeout=15.0)
    except AgentOfflineError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "agent_offline") from e
    except asyncio.TimeoutError as e:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "agent_timeout") from e

    if not resp.get("ok"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, resp.get("error", "agent_error"))
    b64 = resp.get("result", {}).get("jpeg_b64", "")
    try:
        jpeg = base64.b64decode(b64)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "invalid jpeg") from e
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=15"},
    )


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    cam = await _owned_camera(camera_id, user, db)
    await db.delete(cam)
    await db.commit()


@router.websocket("/{camera_id}/live")
async def camera_live(ws: WebSocket, camera_id: UUID, token: str = Query(...)) -> None:
    """Live MJPEG stream proxied from the on-prem agent. Browser sends JWT in
    query (WS can't carry Authorization header). API resolves camera ownership,
    asks the agent to start the ffmpeg pipe, broadcasts incoming frames as
    binary WS messages."""
    try:
        claims = verify_token(token)
        user_id = claims["sub"]
    except Exception:  # noqa: BLE001
        await ws.close(code=4401)
        return

    async with SessionLocal() as db:
        stmt = (
            select(Camera, Device)
            .join(Device, Camera.device_id == Device.id)
            .where(Camera.id == camera_id, Device.owner_id == user_id)
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            await ws.close(code=4404)
            return
        cam, device = row
        rtsp_url = decrypt(cam.rtsp_url_encrypted)
        device_id = str(device.id)

    if not registry.is_online(device_id):
        await ws.close(code=4409)
        return

    await ws.accept()
    await registry.add_viewer(str(camera_id), device_id, rtsp_url, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await registry.remove_viewer(str(camera_id), ws)
