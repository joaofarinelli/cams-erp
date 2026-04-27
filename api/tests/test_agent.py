from httpx import AsyncClient


async def test_heartbeat_updates_last_heartbeat(
    device_client: AsyncClient, seed_device, db_session
) -> None:
    payload = {
        "cameras_status": {},
        "cpu_pct": 5.0,
        "ram_mb": 380,
        "disk_free_mb": 9999,
        "agent_version": "0.1.0",
    }
    r = await device_client.post("/agent/heartbeat", json=payload)
    assert r.status_code == 200
    assert "config_etag" in r.json()


async def test_get_agent_config_returns_owner_cameras(
    device_client: AsyncClient, seed_camera
) -> None:
    r = await device_client.get("/agent/config")
    assert r.status_code == 200
    body = r.json()
    assert "cameras" in body
    assert len(body["cameras"]) == 1
    assert body["cameras"][0]["rtsp_url"]
