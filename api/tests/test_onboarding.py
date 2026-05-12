from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient


async def test_discover_requires_device(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/onboarding/cameras/discover", json={})
    assert r.status_code == 422


async def test_discover_unknown_device_404(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/onboarding/cameras/discover", json={"device_id": str(uuid4())}
    )
    assert r.status_code == 404


async def test_discover_proxies_to_agent(auth_client: AsyncClient, seed_device, monkeypatch) -> None:
    fake_resp = {
        "ok": True,
        "result": {
            "devices": [
                {
                    "ip": "192.168.0.42",
                    "name": "Office cam",
                    "vendor": "intelbras",
                    "xaddrs": ["http://192.168.0.42:8000/onvif/device_service"],
                    "url_templates": [
                        {"label": "Main", "url": "rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"}
                    ],
                }
            ]
        },
    }
    with patch(
        "app.routers.onboarding.registry.call",
        AsyncMock(return_value=fake_resp),
    ):
        r = await auth_client.post(
            "/onboarding/cameras/discover", json={"device_id": str(seed_device.id)}
        )
    assert r.status_code == 200
    devs = r.json()["devices"]
    assert len(devs) == 1
    assert devs[0]["ip"] == "192.168.0.42"


async def test_discover_agent_offline_409(auth_client: AsyncClient, seed_device) -> None:
    from app.services.agent_control import AgentOfflineError

    with patch(
        "app.routers.onboarding.registry.call",
        AsyncMock(side_effect=AgentOfflineError(str(seed_device.id))),
    ):
        r = await auth_client.post(
            "/onboarding/cameras/discover", json={"device_id": str(seed_device.id)}
        )
    assert r.status_code == 409


async def test_probe_proxies_to_agent(auth_client: AsyncClient, seed_device) -> None:
    fake_resp = {
        "ok": True,
        "result": {
            "ok": True,
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 15.0,
            "preview_data_url": "data:image/jpeg;base64,abc",
        },
    }
    with patch(
        "app.routers.onboarding.registry.call",
        AsyncMock(return_value=fake_resp),
    ):
        r = await auth_client.post(
            "/onboarding/cameras/probe",
            json={"device_id": str(seed_device.id), "rtsp_url": "rtsp://x:y@1.2.3.4/main"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["codec"] == "h264"


async def test_templates_returns_known_vendors(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/onboarding/cameras/templates")
    assert r.status_code == 200
    vendors = r.json()["vendors"]
    assert "intelbras" in vendors
    assert "hikvision" in vendors
    assert "generic" in vendors
