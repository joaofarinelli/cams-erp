"""Fan-out for owner notifications: WhatsApp via Evolution API v2 + mobile push via Expo.

Both transports are best-effort, fire-and-forget. A delivery failure must
not break the alert pipeline — exceptions are logged and swallowed."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Subscriber, SubscriberKind

log = logging.getLogger("notifications")

_DIGITS = re.compile(r"\D+")


def _normalize_phone(raw: str) -> str:
    """Evolution API expects E.164 digits-only, e.g. '5511999999999'."""
    return _DIGITS.sub("", raw)


async def _send_whatsapp(client: httpx.AsyncClient, phone: str, body: str) -> None:
    s = get_settings()
    if not s.evolution_api_key:
        log.warning("evolution_api_key not configured; skipping whatsapp send")
        return
    url = f"{s.evolution_base_url.rstrip('/')}/message/sendText/{s.evolution_instance}"
    payload = {"number": _normalize_phone(phone), "text": body}
    try:
        r = await client.post(
            url, json=payload, headers={"apikey": s.evolution_api_key}, timeout=15
        )
        if r.status_code >= 300:
            log.warning("whatsapp send %s -> %s %s", phone, r.status_code, r.text[:200])
    except httpx.HTTPError as e:
        log.warning("whatsapp send error: %r", e)


async def _send_expo(client: httpx.AsyncClient, token: str, title: str, body: str, data: dict) -> None:
    s = get_settings()
    payload = [{"to": token, "title": title, "body": body, "data": data, "sound": "default"}]
    try:
        r = await client.post(s.expo_push_url, json=payload, timeout=15)
        if r.status_code >= 300:
            log.warning("expo push %s -> %s %s", token[:20], r.status_code, r.text[:200])
    except httpx.HTTPError as e:
        log.warning("expo push error: %r", e)


def _build_message(rule_name: str | None, preset_type: str, score: float, message: str) -> tuple[str, str]:
    """Returns (short title, longer body) for both transports."""
    label = rule_name or preset_type
    title = f"🚨 {label}  (score {score:.2f})"
    body = message
    return title, body


async def fan_out_alert(
    db: AsyncSession,
    *,
    owner_id,
    rule_name: str | None,
    preset_type: str,
    score: float,
    message: str,
    alert_id: str,
) -> None:
    """Send the alert to every enabled subscriber for this owner.

    Best-effort. Errors are logged; the calling /alerts/_internal handler
    keeps returning 201."""
    result = await db.execute(
        select(Subscriber).where(
            Subscriber.owner_id == owner_id, Subscriber.enabled.is_(True)
        )
    )
    subs = list(result.scalars().all())
    if not subs:
        return

    title, body = _build_message(rule_name, preset_type, score, message)
    data = {"alert_id": alert_id}

    async with httpx.AsyncClient() as client:
        tasks = []
        for sub in subs:
            if sub.kind == SubscriberKind.whatsapp:
                tasks.append(_send_whatsapp(client, sub.target, f"*{title}*\n{body}"))
            elif sub.kind == SubscriberKind.expo_push:
                tasks.append(_send_expo(client, sub.target, title, body, data))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
