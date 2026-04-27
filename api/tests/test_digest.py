from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.db.models import Alert, Event, PresetType, Rule


async def test_digest_run_now_with_no_alerts(auth_client: AsyncClient, monkeypatch) -> None:
    await auth_client.post("/me/subscribers", json={"kind": "whatsapp", "target": "5511999991234"})
    sent_wa = AsyncMock()
    monkeypatch.setattr("app.services.digest._send_whatsapp", sent_wa)
    monkeypatch.setattr("app.services.digest._send_expo", AsyncMock())

    r = await auth_client.post("/digest/run-now")
    assert r.status_code == 200
    assert r.json() == {"sent": True}
    sent_wa.assert_awaited_once()
    body = sent_wa.await_args.args[2]
    assert "Nenhum alerta" in body
    assert "🟢" in body


async def test_digest_run_now_without_subscribers_sends_nothing(
    auth_client: AsyncClient, monkeypatch
) -> None:
    sent_wa = AsyncMock()
    monkeypatch.setattr("app.services.digest._send_whatsapp", sent_wa)
    monkeypatch.setattr("app.services.digest._send_expo", AsyncMock())

    r = await auth_client.post("/digest/run-now")
    assert r.status_code == 200
    assert r.json() == {"sent": False}
    sent_wa.assert_not_awaited()


async def test_digest_run_now_aggregates_recent_alerts(
    auth_client: AsyncClient, seed_camera, db_session, monkeypatch
) -> None:
    await auth_client.post("/me/subscribers", json={"kind": "whatsapp", "target": "5511999991234"})

    rule = Rule(
        camera_id=seed_camera.id,
        preset_type=PresetType.cash_register,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
        name="Toque no balcao",
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
    # Two recent alerts + one older than 24h that should NOT appear
    db_session.add(
        Alert(rule_id=rule.id, event_id=event.id, score=0.91, message="Mao na gaveta no frame 2")
    )
    db_session.add(
        Alert(rule_id=rule.id, event_id=event.id, score=0.83, message="Operador suspeito (frame 0)")
    )
    old = Alert(
        rule_id=rule.id,
        event_id=event.id,
        score=0.7,
        message="alerta velho — fora da janela",
    )
    db_session.add(old)
    await db_session.flush()
    old.created_at = datetime.now(tz=timezone.utc) - timedelta(hours=30)
    await db_session.commit()

    sent_wa = AsyncMock()
    monkeypatch.setattr("app.services.digest._send_whatsapp", sent_wa)
    monkeypatch.setattr("app.services.digest._send_expo", AsyncMock())

    r = await auth_client.post("/digest/run-now")
    assert r.status_code == 200
    assert r.json() == {"sent": True}

    sent_wa.assert_awaited_once()
    body = sent_wa.await_args.args[2]
    assert "resumo diário" in body
    assert "*2*" in body  # last 24h count
    assert "Toque no balcao" in body
    assert "alerta velho" not in body
