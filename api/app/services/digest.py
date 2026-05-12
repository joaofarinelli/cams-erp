"""Daily digest: top alerts of the last 24h, grouped by rule, sent via WA + push.

Runs once a day in the API process via a tiny asyncio cron loop in the
FastAPI lifespan. Best-effort and idempotent enough — at-least-once delivery
is preferable to silence."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Alert, AlertStatus, Camera, Device, Rule, Subscriber, SubscriberKind, User
from app.db.session import SessionLocal
from app.services.notifications import _send_expo, _send_whatsapp

log = logging.getLogger("digest")


def _format_digest(owner_label: str, alerts_with_meta: list[dict]) -> tuple[str, str]:
    """Returns (whatsapp body, push body). Same content, different formatting."""
    if not alerts_with_meta:
        wa = (
            f"*cams-erp · resumo diário*\n"
            f"Olá! Nenhum alerta foi disparado nas últimas 24h. Tudo tranquilo. 🟢"
        )
        return wa, "Sem alertas nas últimas 24h."

    # Group by rule for the WA body
    grouped: dict[str, list[dict]] = defaultdict(list)
    for a in alerts_with_meta:
        key = a["rule_name"] or "Sem nome"
        grouped[key].append(a)

    pending = sum(1 for a in alerts_with_meta if a["status"] == AlertStatus.pending.value)
    fp = sum(1 for a in alerts_with_meta if a["status"] == AlertStatus.false_positive.value)

    lines = [
        f"*cams-erp · resumo diário*",
        f"Últimas 24h: *{len(alerts_with_meta)}* alertas, {pending} pendentes, {fp} marcados falso-positivo.",
        "",
    ]
    for rule_label, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
        top = items[0]
        cam = top["camera_name"]
        when = datetime.fromisoformat(top["created_at"]).strftime("%d/%m %H:%M")
        lines.append(f"• *{rule_label}* — {len(items)}x  ({cam}, último {when})")
        lines.append(f"  {top['message'][:140]}")
    lines.append("")
    lines.append("Abra o app pra revisar e dar feedback.")
    return "\n".join(lines), f"{len(alerts_with_meta)} alertas nas últimas 24h. Toque para revisar."


async def build_owner_digest(db: AsyncSession, owner_id) -> list[dict]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    stmt = (
        select(Alert, Rule, Camera)
        .join(Rule, Alert.rule_id == Rule.id)
        .join(Camera, Rule.camera_id == Camera.id)
        .join(Device, Camera.device_id == Device.id)
        .where(Device.owner_id == owner_id, Alert.created_at >= cutoff)
        .order_by(Alert.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(a.id),
            "rule_name": r.name,
            "camera_name": c.name,
            "status": a.status.value,
            "score": a.score,
            "message": a.message,
            "created_at": a.created_at.isoformat(),
        }
        for (a, r, c) in rows
    ]


async def run_digest_for_owner(db: AsyncSession, owner: User) -> bool:
    """Returns True if any digest was sent."""
    alerts = await build_owner_digest(db, owner.id)

    subs = (
        await db.execute(
            select(Subscriber).where(
                Subscriber.owner_id == owner.id, Subscriber.enabled.is_(True)
            )
        )
    ).scalars().all()
    if not subs:
        return False

    wa_body, push_body = _format_digest(owner.email or str(owner.id), alerts)
    title = "cams-erp · resumo diário"

    async with httpx.AsyncClient() as client:
        tasks = []
        for sub in subs:
            if sub.kind == SubscriberKind.whatsapp:
                tasks.append(_send_whatsapp(client, sub.target, wa_body))
            elif sub.kind == SubscriberKind.expo_push:
                tasks.append(_send_expo(client, sub.target, title, push_body, {"kind": "digest"}))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    return True


async def run_digest_now() -> dict:
    """Manual trigger / scheduled entry point. Iterates every user that owns
    devices and dispatches their digest in parallel."""
    settings = get_settings()
    if not settings.digest_enabled:
        return {"sent": 0, "skipped": "digest_enabled=False"}

    sent = 0
    async with SessionLocal() as db:
        owners = (
            await db.execute(
                select(User)
                .join(Device, Device.owner_id == User.id)
                .group_by(User.id)
            )
        ).scalars().all()
        for owner in owners:
            try:
                ok = await run_digest_for_owner(db, owner)
                if ok:
                    sent += 1
            except Exception as e:  # noqa: BLE001
                log.warning("digest for owner %s failed: %r", owner.id, e)
    log.info("digest run complete: %d owners notified", sent)
    return {"sent": sent}


def _seconds_until_next(hour: int, tz_name: str) -> float:
    """Seconds from now until the next occurrence of `hour:00` in tz_name."""
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    target = now_local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now_local:
        target += timedelta(days=1)
    return (target - now_local).total_seconds()


async def digest_scheduler() -> None:
    """Long-running asyncio task. Sleeps until the configured hour and dispatches.

    Survives errors in run_digest_now — never lets the loop die."""
    settings = get_settings()
    if not settings.digest_enabled:
        log.info("digest disabled by config, scheduler exiting")
        return
    log.info(
        "digest scheduler armed for %02d:00 %s",
        settings.digest_hour_local,
        settings.digest_timezone,
    )
    while True:
        try:
            wait = _seconds_until_next(settings.digest_hour_local, settings.digest_timezone)
            await asyncio.sleep(wait)
            await run_digest_now()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("digest scheduler tick failed: %r", e)
            await asyncio.sleep(60)  # back off briefly before retrying
