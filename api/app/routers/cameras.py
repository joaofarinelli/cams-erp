from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, User
from app.db.session import get_db
from app.schemas.cameras import CameraCreate, CameraOut, CameraUpdate
from app.security.cognito import get_current_user
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


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    cam = await _owned_camera(camera_id, user, db)
    await db.delete(cam)
    await db.commit()
