"""Per-rule activation windows.

Schedule shape:
{
  "timezone": "America/Sao_Paulo",
  "windows": [
    {"days": [0,1,2,3,4,5,6], "start": "18:00", "end": "23:59"},
    {"days": [0,1,2,3,4,5,6], "start": "00:00", "end": "06:00"}
  ]
}

days: 0=Mon..6=Sun (Python weekday()).
start/end: "HH:MM" local-time strings. end can be "23:59" — keep it inclusive.
None / missing schedule == always active.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def is_active_now(schedule: dict | None, now: datetime | None = None) -> bool:
    if not schedule:
        return True
    tz_name = schedule.get("timezone") or "America/Sao_Paulo"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    local = (now or datetime.now(tz)).astimezone(tz)
    weekday = local.weekday()
    cur = local.time()
    for w in schedule.get("windows") or []:
        days = w.get("days") or list(range(7))
        if weekday not in days:
            continue
        try:
            start = _parse_hhmm(w["start"])
            end = _parse_hhmm(w["end"])
        except (KeyError, ValueError):
            continue
        if start <= end:
            if start <= cur <= end:
                return True
        else:  # window crosses midnight, e.g. 22:00 -> 06:00
            if cur >= start or cur <= end:
                return True
    return False
