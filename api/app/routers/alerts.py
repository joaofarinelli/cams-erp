from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Alert, AlertStatus, Camera, Device, Event, PresetType, Rule, User
from app.db.session import get_db
from app.schemas.alerts import AlertOut
from app.security.cognito import get_current_user
from app.services.notifications import fan_out_alert
from app.services.pubsub import broker


class InternalAlertCreate(BaseModel):
    rule_id: UUID
    event_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    message: str = Field(min_length=1, max_length=512)

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
            rule_name=r.name,
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
        rule_name=r.name,
        event_id=a.event_id,
        camera_id=r.camera_id,
        preset_type=r.preset_type,
        status=a.status,
        score=a.score,
        message=a.message,
        s3_key=e.s3_key,
        created_at=a.created_at,
    )


@router.post("/_internal", status_code=201)
async def create_internal_alert(
    payload: InternalAlertCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Inference-worker entrypoint. Persists the Alert and publishes to the
    in-process broker so connected mobile WS clients receive a push.

    Gated by CAMS_AUTH_BYPASS so it can't be called from the public internet
    in a dev tunnel. In production, replace with mTLS or an internal-only
    network path."""
    if not get_settings().auth_bypass:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    stmt = (
        select(Rule, Camera, Device)
        .join(Camera, Rule.camera_id == Camera.id)
        .join(Device, Camera.device_id == Device.id)
        .where(Rule.id == payload.rule_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    rule, camera, device = row

    alert = Alert(
        rule_id=payload.rule_id,
        event_id=payload.event_id,
        score=payload.score,
        message=payload.message,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    await broker.publish(
        device.owner_id,
        {
            "type": "alert",
            "id": str(alert.id),
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "camera_id": str(camera.id),
            "preset_type": rule.preset_type.value,
            "score": payload.score,
            "message": payload.message,
            "created_at": alert.created_at.isoformat(),
        },
    )
    await fan_out_alert(
        db,
        owner_id=device.owner_id,
        rule_name=rule.name,
        preset_type=rule.preset_type.value,
        score=payload.score,
        message=payload.message,
        alert_id=str(alert.id),
    )
    return {"id": str(alert.id)}


@router.websocket("/stream")
async def alerts_stream(ws: WebSocket, user: User = Depends(get_current_user)) -> None:
    await ws.accept()
    q = await broker.subscribe(user.id)
    try:
        while True:
            payload = await q.get()
            await ws.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        await broker.unsubscribe(user.id, q)
