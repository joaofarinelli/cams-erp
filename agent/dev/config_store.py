"""Persistent agent config in %LOCALAPPDATA%\\cams-agent\\config.json.

The `device_token` value is encrypted at rest with Fernet using a key
derived from the host's hardware UUID (Windows: `wmic csproduct get uuid`,
others: hostname + uname). If the host UUID changes (PC swap, reinstall),
decryption fails and we fall back to clearing the bad value — the user is
re-prompted via the pairing GUI. All other fields stay in cleartext.

Replaces the env-driven .bat workflow. First launch: the GUI prompts for a
pair code; once paired we save the device token here and never ask again.
Subsequent launches read this file. The web panel handles everything else
(cameras, rules, edge_yolo toggle), so the local file stays tiny.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

APP_NAME = "cams-agent"
DEFAULT_API = "https://cams-erp-api.fly.dev"
_TOKEN_PREFIX = "enc:v1:"


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


def _hardware_seed() -> str:
    """Stable per-host secret. Windows uses the BIOS UUID; other OSes a
    hostname+kernel mix. Not crypto-strong, but it forces an attacker who
    copies just the config.json (without the PC) to fail the decrypt."""
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["wmic", "csproduct", "get", "uuid"],
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                line = line.strip()
                if line and line.upper() != "UUID":
                    return f"win:{line}"
        except Exception:  # noqa: BLE001
            pass
    return f"{platform.node()}:{platform.system()}:{platform.machine()}"


def _fernet_key() -> bytes:
    seed = (_hardware_seed() + ":cams-erp-agent-v1").encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    return base64.urlsafe_b64encode(digest)


def _encrypt_token(plain: str) -> str:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return plain  # cryptography missing — degrade to plaintext
    f = Fernet(_fernet_key())
    return _TOKEN_PREFIX + f.encrypt(plain.encode("utf-8")).decode("ascii")


def _decrypt_token(stored: str) -> str | None:
    if not stored.startswith(_TOKEN_PREFIX):
        return stored  # legacy plaintext, accept as-is
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:
        return None
    f = Fernet(_fernet_key())
    try:
        return f.decrypt(stored[len(_TOKEN_PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None


def load_config() -> dict[str, Any]:
    """Returns dict (possibly empty). Never raises — corrupt file -> empty.
    Transparently decrypts the device_token field."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if "device_token" in data:
        plain = _decrypt_token(data["device_token"])
        if plain is None:
            # Decrypt failed (HW changed, file copied from another machine).
            # Drop the bad token; caller will re-pair.
            data.pop("device_token", None)
        else:
            data["device_token"] = plain
    return data


def save_config(data: dict[str, Any]) -> None:
    p = config_path()
    out = dict(data)
    if "device_token" in out and out["device_token"]:
        out["device_token"] = _encrypt_token(out["device_token"])
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
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
