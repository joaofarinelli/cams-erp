"""Persistent agent config in %LOCALAPPDATA%\\cams-agent\\config.json.

Replaces the env-driven .bat workflow. First launch: the GUI prompts for a
pair code; once paired we save the device token here and never ask again.
Subsequent launches read this file. The web panel handles everything else
(cameras, rules, edge_yolo toggle), so the local file stays tiny.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "cams-agent"
DEFAULT_API = "https://cams-erp-api.fly.dev"


def config_dir() -> Path:
    """Per-user dir, no admin needed. Windows -> %LOCALAPPDATA%\\cams-agent;
    other OSes get ~/.config/cams-agent so dev on macOS/Linux works the same."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Returns dict (possibly empty). Never raises — corrupt file -> empty."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict[str, Any]) -> None:
    p = config_path()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def auto_migrate_env() -> dict[str, Any] | None:
    """Legacy clients had CAMS_DEVICE_TOKEN set in run-agent.bat. If the env is
    populated but no config file exists yet, migrate transparently so we don't
    re-prompt for pairing after an upgrade."""
    token = os.environ.get("CAMS_DEVICE_TOKEN", "").strip()
    if not token:
        return None
    existing = load_config()
    if existing.get("device_token"):
        return existing
    cfg = {
        "api_base": os.environ.get("CAMS_API", DEFAULT_API).rstrip("/"),
        "device_token": token,
    }
    save_config(cfg)
    return cfg


def clear_config() -> None:
    """For the 'Reset pairing' tray action."""
    p = config_path()
    if p.exists():
        p.unlink()
