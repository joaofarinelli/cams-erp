from httpx import AsyncClient


_PROMPT = "Detectar abertura da gaveta do caixa em horario suspeito"


async def test_create_rule_for_cash_register(auth_client: AsyncClient, seed_camera) -> None:
    payload = {
        "camera_id": str(seed_camera.id),
        "zones": {
            "gaveta": [[0.1, 0.5], [0.4, 0.5], [0.4, 0.9], [0.1, 0.9]],
            "pc_operador": [[0.6, 0.1], [0.9, 0.1], [0.9, 0.5], [0.6, 0.5]],
        },
        "custom_prompt": _PROMPT,
    }
    r = await auth_client.post("/rules", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["enabled"] is True


async def test_list_rules_for_owner(auth_client: AsyncClient, seed_camera) -> None:
    r = await auth_client.post(
        "/rules",
        json={
            "camera_id": str(seed_camera.id),
            "zones": {"gaveta": [[0, 0], [1, 0], [1, 1]], "pc_operador": [[0, 0], [1, 0], [1, 1]]},
            "custom_prompt": _PROMPT,
        },
    )
    rule_id = r.json()["id"]
    r = await auth_client.get("/rules")
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == rule_id


async def test_update_rule_toggles_enabled(auth_client: AsyncClient, seed_camera) -> None:
    r = await auth_client.post(
        "/rules",
        json={
            "camera_id": str(seed_camera.id),
            "zones": {"gaveta": [[0, 0], [1, 0], [1, 1]], "pc_operador": [[0, 0], [1, 0], [1, 1]]},
            "custom_prompt": _PROMPT,
        },
    )
    rid = r.json()["id"]
    r = await auth_client.put(f"/rules/{rid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False


async def test_invalid_zone_polygon_rejected(auth_client: AsyncClient, seed_camera) -> None:
    r = await auth_client.post(
        "/rules",
        json={
            "camera_id": str(seed_camera.id),
            "zones": {"gaveta": [[0, 0], [1, 1]]},  # only 2 points
            "custom_prompt": _PROMPT,
        },
    )
    assert r.status_code == 422
