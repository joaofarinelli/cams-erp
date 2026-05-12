from datetime import datetime, timezone

from httpx import AsyncClient

from app.db.models import Alert, Event, Rule


async def test_list_alerts_returns_owners_only(
    auth_client: AsyncClient, seed_camera, db_session
) -> None:
    rule = Rule(
        camera_id=seed_camera.id,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
        custom_prompt="Detectar comportamento descrito",
    )
    db_session.add(rule)
    await db_session.flush()
    event = Event(
        camera_id=seed_camera.id,
        s3_key="clips/x.mp4",
        motion_score=0.5,
        started_at=datetime.now(tz=timezone.utc),
        duration_ms=10000,
    )
    db_session.add(event)
    await db_session.flush()
    alert = Alert(rule_id=rule.id, event_id=event.id, score=0.91, message="Suspect at register")
    db_session.add(alert)
    await db_session.commit()

    r = await auth_client.get("/alerts")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["s3_key"] == "clips/x.mp4"
