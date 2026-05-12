"""Handle inbound WhatsApp replies from the Evolution API webhook.

Wire on Evolution side: Manager UI > instance settings > Webhook > URL =
https://<your-public-host>/webhooks/evolution
events = MESSAGES_UPSERT (the only one we use)

Reply semantics (case-insensitive, accents stripped):
  ok | sim | s | confirmar | 1 | 👍 | ✅      -> seen
  fp | falso | nao | n | falso positivo | 0 | 👎 | ❌  -> false_positive

If the inbound number maps to a known Subscriber, we update the most recent
PENDING alert for that owner. The user gets a confirmation reply via the same
Evolution instance so the loop is closed in WhatsApp.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Alert, AlertStatus, Camera, Device, Rule, Subscriber, SubscriberKind
from app.services.notifications import _send_whatsapp

log = logging.getLogger("whatsapp_inbound")

POSITIVE = {"ok", "sim", "s", "yes", "y", "confirmar", "confirmo", "1", "👍", "✅", "✓"}
NEGATIVE = {
    "fp", "falso", "falsopositivo", "nao", "n", "no", "0", "👎", "❌", "x",
    "errado", "erro",
}


def _normalize(text: str) -> str:
    s = (text or "").strip().lower()
    return re.sub(r"\s+", "", s)


def _ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _classify(text: str) -> AlertStatus | None:
    norm = _normalize(text)
    if not norm:
        return None
    candidates = {c for c in {norm, _ascii_fold(norm)} if c}
    for c in candidates:
        if c in POSITIVE:
            return AlertStatus.seen
        if c in NEGATIVE:
            return AlertStatus.false_positive
    if candidates and max(len(c) for c in candidates) <= 14:
        for c in candidates:
            for k in POSITIVE:
                if k and k in c:
                    return AlertStatus.seen
            for k in NEGATIVE:
                if k and k in c:
                    return AlertStatus.false_positive
    return None


def _extract_message(payload: dict[str, Any]) -> tuple[str, str] | None:
    """Pull (sender phone, text) out of an Evolution v2 webhook body. Evolution
    payloads vary by version; we accept a few shapes."""
    data = payload.get("data") or payload
    # MESSAGES_UPSERT shape
    key = data.get("key", {})
    remote_jid = key.get("remoteJid") or data.get("remoteJid") or ""
    from_me = key.get("fromMe", data.get("fromMe", False))
    if from_me:
        return None
    if not remote_jid:
        return None
    phone = remote_jid.split("@")[0]
    msg = data.get("message") or {}
    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("ephemeralMessage") or {}).get("message", {}).get("conversation")
        or data.get("text")
        or ""
    )
    if not text:
        return None
    return phone, text


async def handle_evolution_webhook(payload: dict, db: AsyncSession) -> dict:
    parsed = _extract_message(payload)
    if parsed is None:
        return {"handled": False, "reason": "no inbound text"}
    phone, text = parsed
    decision = _classify(text)
    if decision is None:
        return {"handled": False, "reason": "no decision keyword in message"}

    sub = (
        await db.execute(
            select(Subscriber).where(
                Subscriber.kind == SubscriberKind.whatsapp,
                Subscriber.target == phone,
                Subscriber.enabled.is_(True),
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        return {"handled": False, "reason": f"unknown phone {phone}"}

    row = (
        await db.execute(
            select(Alert, Rule)
            .join(Rule, Alert.rule_id == Rule.id)
            .join(Camera, Rule.camera_id == Camera.id)
            .join(Device, Camera.device_id == Device.id)
            .where(
                Device.owner_id == sub.owner_id,
                Alert.status == AlertStatus.pending,
            )
            .order_by(Alert.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        await _reply(phone, "Não encontrei alerta pendente pra atualizar. Tudo limpo. ✅")
        return {"handled": False, "reason": "no pending alert"}

    alert, rule = row
    alert.status = decision
    await db.commit()

    label = rule.name or "Sem nome"
    if decision == AlertStatus.seen:
        body = f"✅ Alerta confirmado: *{label}*. Obrigado!"
    else:
        body = f"❌ Alerta marcado como falso positivo: *{label}*. Vou aprender com isso."
    await _reply(phone, body)
    return {"handled": True, "alert_id": str(alert.id), "status": decision.value}


async def _reply(phone: str, body: str) -> None:
    s = get_settings()
    if not s.evolution_api_key:
        return
    async with httpx.AsyncClient() as client:
        try:
            await _send_whatsapp(client, phone, body)
        except Exception as e:  # noqa: BLE001
            log.warning("reply send failed: %r", e)
