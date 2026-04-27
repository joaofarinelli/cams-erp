from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, AlertStatus, Camera, Device, Event, PresetType, Rule, User
from app.db.session import get_db
from app.schemas.alerts import AlertOut
from app.security.cognito import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    since: datetime | None = Query(default=None),
    camera_id: UUID | None = Query(default=None),
    preset_type: PresetType | None = Query(default=None),
    limit: int = Query(default=50, le=500),
) -> list[AlertOut]:
    stmt = (
        select(Alert, Rule, Event)
        .join(Rule, Alert.rule_id == Rule.id)
        .join(Event, Alert.event_id == Event.id)
        .join(Camera, Rule.camera_id == Camera.id)
        .join(Device, Camera.device_id == Device.id)
        .where(Device.owner_id == user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(Alert.created_at >= since)
    if camera_id is not None:
        stmt = stmt.where(Camera.id == camera_id)
    if preset_type is not None:
        stmt = stmt.where(Rule.preset_type == preset_type)

    rows = (await db.execute(stmt)).all()
    return [
        AlertOut(
            id=a.id,
            rule_id=a.rule_id,
            event_id=a.event_id,
            camera_id=r.camera_id,
            preset_type=r.preset_type,
            status=a.status,
            score=a.score,
            message=a.message,
            s3_key=e.s3_key,
            created_at=a.created_at,
        )
        for (a, r, e) in rows
    ]


@router.post("/{alert_id}/feedback", response_model=AlertOut)
async def feedback(
    alert_id: UUID,
    is_false_positive: bool,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlertOut:
    stmt = (
        select(Alert, Rule, Event)
        .join(Rule, Alert.rule_id == Rule.id)
        .join(Event, Alert.event_id == Event.id)
        .join(Camera, Rule.camera_id == Camera.id)
        .join(Device, Camera.device_id == Device.id)
        .where(Alert.id == alert_id, Device.owner_id == user.id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    a, r, e = row
    a.status = AlertStatus.false_positive if is_false_positive else AlertStatus.seen
    await db.commit()
    await db.refresh(a)
    return AlertOut(
        id=a.id,
        rule_id=a.rule_id,
        event_id=a.event_id,
        camera_id=r.camera_id,
        preset_type=r.preset_type,
        status=a.status,
        score=a.score,
        message=a.message,
        s3_key=e.s3_key,
        created_at=a.created_at,
    )
