"""Sends agent crashes to the cloud (POST /agent/errors).

Buffers reports in memory when the API is unreachable so we don't lose
them during connectivity blips; replays them on the next successful call.
Also writes a copy to agent.log so local debugging still works offline.
"""

from __future__ import annotations

import threading
import traceback as tb_mod
from collections import deque
from datetime import datetime
from typing import Any

import httpx


_BUFFER: deque[dict] = deque(maxlen=200)
_LOCK = threading.Lock()
_CFG: Any | None = None
_AGENT_VERSION: str = "dev"


def configure(cfg: Any, agent_version: str = "dev") -> None:
    """Wire the reporter to an AgentConfig instance (gives api_base + token)
    and an agent build version string. Idempotent."""
    global _CFG, _AGENT_VERSION
    _CFG = cfg
    _AGENT_VERSION = agent_version


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [crash-report] {msg}", flush=True)


def _flush_locked() -> None:
    if _CFG is None or not _BUFFER:
        return
    try:
        api_base = _CFG.api_base
        token = _CFG.device_token
    except AttributeError:
        return
    headers = {"X-Device-Token": token}
    while _BUFFER:
        payload = _BUFFER[0]
        try:
            r = httpx.post(
                f"{api_base}/agent/errors", json=payload, headers=headers, timeout=5
            )
            if r.status_code in (200, 201, 202):
                _BUFFER.popleft()
            else:
                # API ack'd reachability but rejected; drop to avoid stuck queue.
                _log(f"server {r.status_code}: dropping report")
                _BUFFER.popleft()
        except Exception as e:  # noqa: BLE001
            _log(f"flush failed: {e!r}; keeping {len(_BUFFER)} buffered")
            return


def report(kind: str, exc: BaseException, context: dict | None = None) -> None:
    """Capture an exception and ship it to the cloud (or buffer if offline)."""
    payload = {
        "kind": kind[:64],
        "message": (str(exc) or exc.__class__.__name__)[:1024],
        "traceback": "".join(tb_mod.format_exception(type(exc), exc, exc.__traceback__))[:20000],
        "agent_version": _AGENT_VERSION,
        "context": context,
    }
    _log(f"{kind}: {payload['message'][:120]}")
    with _LOCK:
        _BUFFER.append(payload)
        _flush_locked()


def heartbeat_flush() -> None:
    """Called from the heartbeat loop on each tick to drain the buffer."""
    with _LOCK:
        _flush_locked()
