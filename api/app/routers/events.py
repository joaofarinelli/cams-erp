from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Event
from app.db.session import get_db
from app.schemas.events import EventCreate, EventOut
from app.security.device_auth import get_current_device
from app.services.quotas import check_quota
from app.services.sqs import enqueue_event
from app.services.usage import increment_usage

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

    # Quota check: hard reject at 110% of tier limit; soft accept between
    # 100% and 110% but mark for skip downstream so VLM doesn't burn budget.
    allowed, current, limit = await check_quota(db, device.owner_id, "events_per_month")
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"events quota exceeded for current plan ({current}/{limit})",
        )
    analysis_skipped = limit is not None and current >= limit  # 100-110% band

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

    await increment_usage(db, device.owner_id, events_count=1)

    if not analysis_skipped:
        enqueue_event(
            {
                "event_id": str(event.id),
                "camera_id": str(event.camera_id),
                "s3_key": event.s3_key,
                "started_at": event.started_at.isoformat(),
                "duration_ms": event.duration_ms,
            }
        )
    return EventOut(id=event.id, enqueued=not analysis_skipped)
