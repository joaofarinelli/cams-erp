from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.schedule import is_active_now


def _at(hour: int, minute: int = 0, weekday: int = 0):
    """Aware dt in America/Sao_Paulo. 2026-04-27 is a Monday."""
    base = datetime(2026, 4, 27, hour, minute, tzinfo=ZoneInfo("America/Sao_Paulo"))
    return base + timedelta(days=weekday)


def test_no_schedule_is_always_active() -> None:
    assert is_active_now(None) is True
    assert is_active_now({}) is True


def test_simple_window() -> None:
    sched = {
        "timezone": "America/Sao_Paulo",
        "windows": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "08:00", "end": "18:00"}],
    }
    assert is_active_now(sched, _at(10)) is True
    assert is_active_now(sched, _at(7, 59)) is False
    assert is_active_now(sched, _at(20)) is False


def test_overnight_window() -> None:
    sched = {
        "timezone": "America/Sao_Paulo",
        "windows": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "22:00", "end": "06:00"}],
    }
    assert is_active_now(sched, _at(23)) is True
    assert is_active_now(sched, _at(2)) is True
    assert is_active_now(sched, _at(12)) is False


def test_weekday_filtering() -> None:
    sched = {
        "timezone": "America/Sao_Paulo",
        "windows": [{"days": [5, 6], "start": "00:00", "end": "23:59"}],
    }
    # weekday 0 = monday, 5 = saturday
    assert is_active_now(sched, _at(10, weekday=0)) is False
    assert is_active_now(sched, _at(10, weekday=5)) is True


def test_invalid_window_silently_ignored() -> None:
    sched = {"windows": [{"days": [0], "start": "bad", "end": "10:00"}]}
    assert is_active_now(sched, _at(5)) is False
