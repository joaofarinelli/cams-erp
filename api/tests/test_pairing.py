from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time
from httpx import AsyncClient


async def test_owner_creates_pair_code(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/pair/code")
    assert r.status_code == 201
    body = r.json()
    assert len(body["pair_code"]) == 6
    assert body["pair_code"].isdigit()


async def test_agent_verifies_code_and_gets_token(auth_client: AsyncClient, anon_client: AsyncClient) -> None:
    r = await auth_client.post("/pair/code")
    code = r.json()["pair_code"]

    r = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r.status_code == 200
    body = r.json()
    assert "device_token" in body
    assert body["device_token"]


async def test_expired_code_is_rejected(auth_client: AsyncClient, anon_client: AsyncClient) -> None:
    with freeze_time(datetime.now(tz=timezone.utc) - timedelta(minutes=15)):
        r = await auth_client.post("/pair/code")
        code = r.json()["pair_code"]

    r = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r.status_code == 400


async def test_code_is_single_use(auth_client: AsyncClient, anon_client: AsyncClient) -> None:
    r = await auth_client.post("/pair/code")
    code = r.json()["pair_code"]
    r1 = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r1.status_code == 200
    r2 = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r2.status_code == 400
