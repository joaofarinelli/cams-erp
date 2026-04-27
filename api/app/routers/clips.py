from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device
from app.db.session import get_db
from app.schemas.clips import ClipUploadRequest, ClipUploadResponse
from app.security.device_auth import get_current_device
from app.services.s3 import signed_put_url

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
