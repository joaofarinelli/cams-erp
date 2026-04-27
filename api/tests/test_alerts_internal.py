from datetime import datetime, timezone

from httpx import AsyncClient

from app.db.models import Event, PresetType, Rule


async def test_internal_alert_persists_and_publishes(
    auth_client: AsyncClient, anon_client: AsyncClient, seed_camera, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("CAMS_AUTH_BYPASS", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    rule = Rule(
        camera_id=seed_camera.id,
        preset_type=PresetType.cash_register,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
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

    payload = {
        "rule_id": str(rule.id),
        "event_id": str(event.id),
        "score": 0.91,
        "message": "Mao na gaveta sem operacao no PC (frame 2)",
    }
    r = await anon_client.post("/alerts/_internal", json=payload)
    assert r.status_code == 201
    alert_id = r.json()["id"]

    r = await auth_client.get("/alerts")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == alert_id
    assert items[0]["score"] == 0.91
    assert items[0]["message"].startswith("Mao na gaveta")
