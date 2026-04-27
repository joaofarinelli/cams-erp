from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


async def test_discover_empty(auth_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr("app.services.discovery.ws_discover", AsyncMock(return_value=[]))
    r = await auth_client.post("/onboarding/cameras/discover")
    assert r.status_code == 200
    assert r.json() == {"devices": []}


async def test_discover_returns_device_with_templates(auth_client: AsyncClient, monkeypatch) -> None:
    fake = [
        {
            "ip": "192.168.0.42",
            "name": "Office cam",
            "vendor": "intelbras",
            "xaddrs": ["http://192.168.0.42:8000/onvif/device_service"],
            "scopes": [],
            "types": "",
        }
    ]
    monkeypatch.setattr("app.routers.onboarding.ws_discover", AsyncMock(return_value=fake))
    r = await auth_client.post("/onboarding/cameras/discover")
    assert r.status_code == 200
    devs = r.json()["devices"]
    assert len(devs) == 1
    assert devs[0]["ip"] == "192.168.0.42"
    assert devs[0]["vendor"] == "intelbras"
    assert any("realmonitor" in t["url"] for t in devs[0]["url_templates"])


async def test_probe_returns_codec_and_preview(auth_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.onboarding.probe_stream",
        AsyncMock(return_value={"ok": True, "codec": "h264", "width": 1280, "height": 720, "fps": 15.0}),
    )
    monkeypatch.setattr(
        "app.routers.onboarding.first_frame_jpeg", AsyncMock(return_value=b"\xff\xd8\xff\xd9")
    )
    r = await auth_client.post(
        "/onboarding/cameras/probe", json={"rtsp_url": "rtsp://x:y@1.2.3.4/main"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["codec"] == "h264"
    assert body["width"] == 1280
    assert body["preview_data_url"].startswith("data:image/jpeg;base64,")


async def test_probe_failure_returns_error(auth_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.onboarding.probe_stream",
        AsyncMock(return_value={"ok": False, "error": "401 Unauthorized"}),
    )
    r = await auth_client.post(
        "/onboarding/cameras/probe", json={"rtsp_url": "rtsp://bad@1.2.3.4/main"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "401" in body["error"]


async def test_templates_returns_known_vendors(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/onboarding/cameras/templates")
    assert r.status_code == 200
    vendors = r.json()["vendors"]
    assert "intelbras" in vendors
    assert "hikvision" in vendors
    assert "generic" in vendors
