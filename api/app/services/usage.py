"""Atomic per-owner / per-month usage counters.

`increment_usage` runs an UPSERT (`INSERT ... ON CONFLICT DO UPDATE`)
so concurrent agents / workers can write without locking the row, and
the running totals never lose a write to a race.

Keys are (owner_id, month=first-of-this-month) — one row per owner per
billing cycle. Storage GB-hours accumulates as float; integer counters
saturate at BIGINT.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_NUMERIC_COLS = {
    "events_count",
    "vlm_calls",
    "vlm_cascade_calls",
    "vlm_tokens_in",
    "vlm_tokens_out",
    "alerts_count",
    "storage_gb_hours",
}


def _first_of_month() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


async def increment_usage(db: AsyncSession, owner_id: UUID, **deltas: float) -> None:
    """Apply additive deltas to the current month's usage row. Creates the
    row on first call. Caller doesn't need to commit — we do."""
    valid = {k: v for k, v in deltas.items() if k in _NUMERIC_COLS and v}
    if not valid:
        return
    params: dict[str, object] = {
        "owner_id": owner_id,
        "month": _first_of_month(),
    }
    for k, v in valid.items():
        params[k] = v
    insert_cols = ", ".join(["owner_id", "month", *valid.keys(), "updated_at"])
    insert_vals = ", ".join(
        [":owner_id", ":month", *[f":{k}" for k in valid.keys()], "now()"]
    )
    update_set = ", ".join(
        [f"{k} = usage_monthly.{k} + EXCLUDED.{k}" for k in valid.keys()]
        + ["updated_at = now()"]
    )
    sql = (
        f"INSERT INTO usage_monthly ({insert_cols}) "
        f"VALUES ({insert_vals}) "
        f"ON CONFLICT (owner_id, month) DO UPDATE SET {update_set}"
    )
    await db.execute(text(sql), params)
    await db.commit()
