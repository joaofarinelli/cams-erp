import asyncio
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Event, User
from app.db.session import get_db
from app.schemas.cameras import CameraCreate, CameraOut, CameraUpdate
from app.security.cognito import get_current_user
from app.services.kms import decrypt, encrypt

CLIPS_DIR = Path("/tmp/cams-erp-clips")

router = APIRouter(prefix="/cameras", tags=["cameras"])


async def _owned_camera(camera_id: UUID, user: User, db: AsyncSession) -> Camera:
    result = await db.execute(
        select(Camera).join(Device).where(Camera.id == camera_id, Device.owner_id == user.id)
    )
    cam = result.scalar_one_or_none()
    if cam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return cam


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

    cam = Camera(
        device_id=device.id,
        name=payload.name,
        rtsp_url_encrypted=encrypt(payload.rtsp_url),
    )
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


@router.put("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    cam = await _owned_camera(camera_id, user, db)
    if payload.name is not None:
        cam.name = payload.name
    if payload.rtsp_url is not None:
        cam.rtsp_url_encrypted = encrypt(payload.rtsp_url)
    await db.commit()
    await db.refresh(cam)
    return cam


@router.get("/{camera_id}/thumb.jpg")
async def camera_thumbnail(
    camera_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a JPEG of the most recent uploaded clip's middle frame.

    Used by the web polygon editor and the camera list. 404 if no clip has
    been uploaded yet for this camera. Extracted with ffmpeg on the fly —
    cheap (<100ms) for short clips."""
    cam = await _owned_camera(camera_id, user, db)
    stmt = (
        select(Event)
        .where(Event.camera_id == cam.id)
        .order_by(Event.created_at.desc())
        .limit(1)
    )
    event = (await db.execute(stmt)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No clip available yet")
    clip_path = CLIPS_DIR / event.s3_key
    if not clip_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clip missing on disk")

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-loglevel", "error",
        "-ss", "1",
        "-i", str(clip_path),
        "-frames:v", "1",
        "-vf", "scale=640:-2",
        "-f", "image2",
        "-c:v", "mjpeg",
        "-y",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"ffmpeg failed: {stderr.decode(errors='replace')[:200]}",
        )
    return Response(
        content=stdout,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=10"},
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
