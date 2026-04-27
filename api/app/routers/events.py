from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Event
from app.db.session import get_db
from app.schemas.events import EventCreate, EventOut
from app.security.device_auth import get_current_device
from app.services.sqs import enqueue_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
async def create_event(
    payload: EventCreate,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    result = await db.execute(
        select(Camera).where(Camera.id == payload.camera_id, Camera.device_id == device.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    event = Event(
        camera_id=payload.camera_id,
        s3_key=payload.s3_key,
        motion_score=payload.motion_score,
        started_at=payload.started_at,
        duration_ms=payload.duration_ms,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    enqueue_event(
        {
            "event_id": str(event.id),
            "camera_id": str(event.camera_id),
            "s3_key": event.s3_key,
            "started_at": event.started_at.isoformat(),
            "duration_ms": event.duration_ms,
        }
    )
    return EventOut(id=event.id, enqueued=True)
