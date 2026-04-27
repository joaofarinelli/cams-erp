from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.db.models import Alert, AlertStatus, Event, PresetType, Rule


async def test_fp_storm_disables_rule_and_notifies(
    auth_client: AsyncClient, seed_camera, db_session, monkeypatch
) -> None:
    monkeypatch.setattr("app.routers.alerts.fan_out_alert", AsyncMock())
    fan_out = AsyncMock()
    monkeypatch.setattr("app.routers.alerts.fan_out_alert", fan_out)

    rule = Rule(
        camera_id=seed_camera.id,
        preset_type=PresetType.cash_register,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
        name="Spammy rule",
    )
    db_session.add(rule)
    await db_session.flush()
    event = Event(
        camera_id=seed_camera.id,
        s3_key="clips/x.mp4",
        motion_score=0.4,
        started_at=datetime.now(tz=timezone.utc),
        duration_ms=3000,
    )
    db_session.add(event)
    await db_session.flush()

    # 6 already-FP alerts (we are about to mark one more, hitting 7/10)
    for _ in range(6):
        a = Alert(
            rule_id=rule.id,
            event_id=event.id,
            score=0.7,
            message="m",
            status=AlertStatus.false_positive,
        )
        db_session.add(a)
    pending = Alert(rule_id=rule.id, event_id=event.id, score=0.85, message="last one")
    db_session.add(pending)
    await db_session.commit()
    await db_session.refresh(pending)

    r = await auth_client.post(f"/alerts/{pending.id}/feedback?is_false_positive=true")
    assert r.status_code == 200

    await db_session.refresh(rule)
    assert rule.enabled is False
    fan_out.assert_awaited_once()
    awaited_msg = fan_out.await_args.kwargs["message"]
    assert "desativada" in awaited_msg.lower()


async def test_below_fp_threshold_does_not_disable(
    auth_client: AsyncClient, seed_camera, db_session, monkeypatch
) -> None:
    monkeypatch.setattr("app.routers.alerts.fan_out_alert", AsyncMock())

    rule = Rule(
        camera_id=seed_camera.id,
        preset_type=PresetType.cash_register,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
        name="Healthy rule",
    )
    db_session.add(rule)
    await db_session.flush()
    event = Event(
        camera_id=seed_camera.id,
        s3_key="clips/x.mp4",
        motion_score=0.4,
        started_at=datetime.now(tz=timezone.utc),
        duration_ms=3000,
    )
    db_session.add(event)
    await db_session.flush()

    # 4 FP, 4 seen, 1 pending; flipping pending -> FP gives 5/10 — under threshold
    for _ in range(4):
        db_session.add(
            Alert(rule_id=rule.id, event_id=event.id, score=0.7, message="m",
                  status=AlertStatus.false_positive)
        )
    for _ in range(4):
        db_session.add(
            Alert(rule_id=rule.id, event_id=event.id, score=0.7, message="m",
                  status=AlertStatus.seen)
        )
    pending = Alert(rule_id=rule.id, event_id=event.id, score=0.85, message="last one")
    db_session.add(pending)
    await db_session.commit()
    await db_session.refresh(pending)

    r = await auth_client.post(f"/alerts/{pending.id}/feedback?is_false_positive=true")
    assert r.status_code == 200
    await db_session.refresh(rule)
    assert rule.enabled is True
