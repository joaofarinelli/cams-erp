from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.db.models import Alert, AlertStatus, Event, PresetType, Rule
from app.services.whatsapp_inbound import _classify, _extract_message


def test_classify_positive_keywords() -> None:
    from app.services.whatsapp_inbound import POSITIVE
    assert _classify("OK") == AlertStatus.seen
    assert _classify("sim") == AlertStatus.seen
    assert _classify("Sim 👍") == AlertStatus.seen
    assert _classify("✅") == AlertStatus.seen


def test_classify_negative_keywords() -> None:
    assert _classify("FP") == AlertStatus.false_positive
    assert _classify("Não") == AlertStatus.false_positive
    assert _classify("falso positivo") == AlertStatus.false_positive
    assert _classify("❌") == AlertStatus.false_positive


def test_classify_unknown_text() -> None:
    assert _classify("oi tudo bem") is None
    assert _classify("") is None


def test_extract_evolution_payload_message() -> None:
    payload = {
        "data": {
            "key": {"remoteJid": "5517992256171@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "OK"},
        }
    }
    parsed = _extract_message(payload)
    assert parsed == ("5517992256171", "OK")


def test_extract_skips_outbound_messages() -> None:
    payload = {
        "data": {
            "key": {"remoteJid": "5517992256171@s.whatsapp.net", "fromMe": True},
            "message": {"conversation": "Test"},
        }
    }
    assert _extract_message(payload) is None


async def test_webhook_marks_pending_alert_seen(
    auth_client: AsyncClient,
    seed_camera,
    db_session,
    monkeypatch,
) -> None:
    sub = await auth_client.post(
        "/me/subscribers", json={"kind": "whatsapp", "target": "5517992256171"}
    )
    assert sub.status_code == 201

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
        motion_score=0.5,
        started_at=datetime.now(tz=timezone.utc),
        duration_ms=3000,
    )
    db_session.add(event)
    await db_session.flush()
    alert = Alert(rule_id=rule.id, event_id=event.id, score=0.92, message="suspeita")
    db_session.add(alert)
    await db_session.commit()

    monkeypatch.setattr("app.services.whatsapp_inbound._send_whatsapp", AsyncMock())

    payload = {
        "data": {
            "key": {"remoteJid": "5517992256171@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "OK"},
        }
    }
    r = await auth_client.post("/webhooks/evolution", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["handled"] is True
    assert body["status"] == AlertStatus.seen.value

    # Refresh alert from DB
    await db_session.refresh(alert)
    assert alert.status == AlertStatus.seen


async def test_webhook_unknown_phone_is_ignored(auth_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr("app.services.whatsapp_inbound._send_whatsapp", AsyncMock())
    payload = {
        "data": {
            "key": {"remoteJid": "5500000000000@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "OK"},
        }
    }
    r = await auth_client.post("/webhooks/evolution", json=payload)
    assert r.status_code == 200
    assert r.json()["handled"] is False
