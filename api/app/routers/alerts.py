from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Alert, AlertStatus, Camera, Device, Event, Rule, User
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

    rows = (await db.execute(stmt)).all()
    return [
        AlertOut(
            id=a.id,
            rule_id=a.rule_id,
            rule_name=r.name,
            event_id=a.event_id,
            camera_id=r.camera_id,
            status=a.status,
            score=a.score,
            message=a.message,
            s3_key=e.s3_key,
            created_at=a.created_at,
        )
        for (a, r, e) in rows
    ]


FP_STORM_WINDOW = 10
FP_STORM_THRESHOLD = 7


async def _maybe_auto_disable_rule_on_fp_storm(
    db: AsyncSession, rule: Rule, *, owner_id
) -> None:
    """If the last FP_STORM_WINDOW alerts for this rule have FP_STORM_THRESHOLD
    or more false positives, disable the rule and notify the owner. Quiet no-op
    if the rule is already disabled."""
    if not rule.enabled:
        return
    recent = (
        await db.execute(
            select(Alert.status)
            .where(Alert.rule_id == rule.id)
            .order_by(Alert.created_at.desc())
            .limit(FP_STORM_WINDOW)
        )
    ).all()
    if len(recent) < FP_STORM_THRESHOLD:
        return
    fp_count = sum(1 for (status_,) in recent if status_ == AlertStatus.false_positive)
    if fp_count < FP_STORM_THRESHOLD:
        return
    rule.enabled = False
    await db.commit()
    label = rule.name or "Sem nome"
    body = (
        f"⚠️ Regra *{label}* desativada automaticamente.\n"
        f"{fp_count} dos últimos {len(recent)} alertas foram marcados falso-positivo. "
        f"Revise zonas/prompt e reative em Regras."
    )
    await fan_out_alert(
        db,
        owner_id=owner_id,
        rule_name=label,
        score=0.0,
        message=body,
        alert_id="fp-storm",
    )


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

    if is_false_positive:
        await _maybe_auto_disable_rule_on_fp_storm(db, r, owner_id=user.id)

    return AlertOut(
        id=a.id,
        rule_id=a.rule_id,
        rule_name=r.name,
        event_id=a.event_id,
        camera_id=r.camera_id,
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
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> dict:
    """Inference-worker entrypoint. Persists the Alert and publishes to the
    in-process broker so connected mobile WS clients receive a push.

    Auth: dev uses CAMS_AUTH_BYPASS; prod requires X-Internal-Token matching
    settings.internal_token (shared secret over Fly internal networking)."""
    settings = get_settings()
    if not settings.auth_bypass:
        if not settings.internal_token or x_internal_token != settings.internal_token:
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
            "score": payload.score,
            "message": payload.message,
            "created_at": alert.created_at.isoformat(),
        },
    )
    await fan_out_alert(
        db,
        owner_id=device.owner_id,
        rule_name=rule.name,
        score=payload.score,
        message=payload.message,
        alert_id=str(alert.id),
    )
    # Push a desktop toast to the agent that owns this camera so the PDV
    # operator sees the alert immediately on the local machine, not just
    # via WhatsApp/mobile.
    try:
        from app.services.agent_control import registry

        agent_ws = registry._sockets.get(str(device.id))
        if agent_ws is not None:
            await agent_ws.send_json(
                {
                    "type": "alert_pushed",
                    "alert_id": str(alert.id),
                    "camera_id": str(camera.id),
                    "rule_name": rule.name or "Alerta",
                    "score": payload.score,
                    "message": payload.message,
                }
            )
    except Exception:  # noqa: BLE001
        pass
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
