"""Native Windows toast notifications.

Tries `win11toast` (lightweight, no admin), falls back to pystray's
built-in `notify` (works on every OS but uses tray balloon, less rich).
On non-Windows we use pystray fallback only.

Usage:
    notifier = get_notifier(tray_icon)
    notifier.notify("Alerta", "Gaveta aberta — Caixa principal", camera_id=...)
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Callable


class _PystrayFallback:
    """Uses pystray.Icon.notify(). Works everywhere pystray works, but is a
    balloon attached to the tray icon, not a real Windows toast."""

    def __init__(self, icon: Any) -> None:
        self._icon = icon

    def notify(self, title: str, body: str, **_kwargs: Any) -> None:
        try:
            self._icon.notify(body, title=title)
        except Exception:  # noqa: BLE001
            pass


class _Win11Toast:
    """Wraps win11toast.toast for richer notifications on Win 10/11."""

    def __init__(self) -> None:
        from win11toast import toast  # type: ignore

        self._toast = toast

    def notify(self, title: str, body: str, **_kwargs: Any) -> None:
        # win11toast is sync but quick; still run in a thread so the agent's
        # control loop never blocks on Windows UI.
        def _send() -> None:
            try:
                self._toast(title, body, app_id="cams-agent")
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_send, daemon=True).start()


def get_notifier(fallback_icon: Any | None = None) -> Any:
    """Returns whichever notifier we can construct on this machine."""
    if sys.platform == "win32":
        try:
            return _Win11Toast()
        except Exception:  # noqa: BLE001
            pass
    if fallback_icon is not None:
        return _PystrayFallback(fallback_icon)

    class _Null:
        def notify(self, *_a: Any, **_kw: Any) -> None:
            return None

    return _Null()
