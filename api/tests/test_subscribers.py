from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.db.models import Event, Rule


async def test_create_list_delete_subscriber(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/me/subscribers", json={"kind": "whatsapp", "target": "+55 11 99999-1234"}
    )
    assert r.status_code == 201
    sub_id = r.json()["id"]

    r = await auth_client.get("/me/subscribers")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["target"] == "+55 11 99999-1234"

    r = await auth_client.delete(f"/me/subscribers/{sub_id}")
    assert r.status_code == 204

    r = await auth_client.get("/me/subscribers")
    assert r.json() == []


async def test_duplicate_subscriber_returns_existing(auth_client: AsyncClient) -> None:
    payload = {"kind": "expo_push", "target": "ExpoPushToken[abc123]"}
    r1 = await auth_client.post("/me/subscribers", json=payload)
    r2 = await auth_client.post("/me/subscribers", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


async def test_internal_alert_fans_out_to_subscribers(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    seed_camera,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CAMS_AUTH_BYPASS", "1")
    from app.config import get_settings

    get_settings.cache_clear()

    # subscriber for the dev user
    await auth_client.post("/me/subscribers", json={"kind": "whatsapp", "target": "5511999991234"})

    rule = Rule(
        camera_id=seed_camera.id,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
        custom_prompt="Detectar comportamento descrito",
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
    await db_session.commit()

    sent = AsyncMock()
    monkeypatch.setattr("app.services.notifications._send_whatsapp", sent)
    monkeypatch.setattr("app.services.notifications._send_expo", AsyncMock())

    r = await anon_client.post(
        "/alerts/_internal",
        json={
            "rule_id": str(rule.id),
            "event_id": str(event.id),
            "score": 0.91,
            "message": "Mao na gaveta no frame 2",
        },
    )
    assert r.status_code == 201
    sent.assert_awaited_once()
    args = sent.await_args.args
    # _send_whatsapp(client, phone, body)
    assert args[1] == "5511999991234"
    assert "Toque no balcao" in args[2]
    assert "Mao na gaveta" in args[2]
