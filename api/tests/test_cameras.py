from httpx import AsyncClient


async def _auth_user(client: AsyncClient, db_session) -> dict[str, str]:
    # Helper that simulates an authenticated user via a test override
    # of get_current_user (set up in conftest as `auth_client` fixture)
    return {"Authorization": "Bearer fake"}


async def test_create_camera_returns_201(auth_client: AsyncClient, seed_device) -> None:
    payload = {
        "name": "Caixa 1",
        "rtsp_url": "rtsp://user:pw@10.0.0.50:554/Streaming/Channels/101",
        "device_id": str(seed_device.id),
    }
    r = await auth_client.post("/cameras", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Caixa 1"
    assert "rtsp_url" not in body  # not exposed
    assert body["online"] is False


async def test_list_cameras_filters_by_owner(auth_client: AsyncClient, seed_device) -> None:
    await auth_client.post(
        "/cameras",
        json={"name": "C1", "rtsp_url": "rtsp://x/1", "device_id": str(seed_device.id)},
    )
    r = await auth_client.get("/cameras")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_camera(auth_client: AsyncClient, seed_device) -> None:
    r = await auth_client.post(
        "/cameras",
        json={"name": "C1", "rtsp_url": "rtsp://x/1", "device_id": str(seed_device.id)},
    )
    cam_id = r.json()["id"]
    r = await auth_client.delete(f"/cameras/{cam_id}")
    assert r.status_code == 204
    r = await auth_client.get("/cameras")
    assert r.json() == []
