"""Self-updater for the Windows agent.

Polls `GET https://api.github.com/repos/{repo}/releases/latest` once an hour
(and on demand from the tray menu). If `tag_name` is newer than
`AGENT_VERSION`, downloads the `cams-agent-windows.zip` asset, extracts it
to a sibling folder, and relaunches the agent so the new version takes over.

Update layout on disk (Windows):

  C:\\cams-agent\\                     <- user-chosen install root
    run-agent.bat                     <- launcher (never overwritten)
    cams-agent-current\\               <- symlink/junction to current version
    cams-agent-v1.0.0\\                <- versioned install (active)
    cams-agent-v1.1.0\\                <- versioned install (new, after update)

We never overwrite the running exe (Windows locks it). A junction swap +
graceful restart is the only safe pattern here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

import httpx


REPO = "joaofarinelli/cams-erp"
ASSET_NAME = "cams-agent-windows.zip"
CHECK_INTERVAL_SECONDS = 3600  # hourly


def _log(msg: str) -> None:
    from datetime import datetime

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [updater] {msg}", flush=True)


def _parse_version(tag: str) -> tuple[int, ...]:
    """v1.2.3 -> (1, 2, 3). Tolerant of pre-release suffixes."""
    s = tag.lstrip("v").split("-")[0]
    parts = []
    for chunk in s.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _install_root() -> Path | None:
    """Where versioned installs live. Only meaningful in a PyInstaller bundle:
    .../cams-agent-vX/cams-agent/cams-agent.exe -> install root is the great
    grandparent. In dev (running from source) we skip auto-update entirely."""
    if not _is_frozen():
        return None
    exe = Path(sys.executable).resolve()
    # exe = .../<install_root>/cams-agent/cams-agent.exe
    return exe.parent.parent.parent


def fetch_latest_release() -> dict | None:
    try:
        r = httpx.get(
            f"https://api.github.com/repos/{REPO}/releases/latest",
            timeout=10,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code != 200:
            _log(f"github {r.status_code}")
            return None
        return r.json()
    except Exception as e:  # noqa: BLE001
        _log(f"fetch failed: {e!r}")
        return None


def _asset_url(release: dict) -> str | None:
    for a in release.get("assets") or []:
        if a.get("name") == ASSET_NAME:
            return a.get("browser_download_url")
    return None


def _download_zip(url: str, dest: Path) -> bool:
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=180) as r:
            if r.status_code != 200:
                _log(f"download HTTP {r.status_code}")
                return False
            with dest.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return True
    except Exception as e:  # noqa: BLE001
        _log(f"download failed: {e!r}")
        return False


def _swap_current(install_root: Path, new_dir: Path) -> bool:
    """Atomically point `<root>/cams-agent-current` at `new_dir`.

    Windows: uses a directory junction (no admin needed, unlike symlinks).
    Falls back to renaming the old current_dir to .bak before linking."""
    current = install_root / "cams-agent-current"
    if current.exists() or current.is_symlink():
        bak = install_root / f"cams-agent-current.bak-{int(time.time())}"
        try:
            current.rename(bak)
        except Exception as e:  # noqa: BLE001
            _log(f"rename old current failed: {e!r}")
            return False
    if sys.platform == "win32":
        try:
            subprocess.check_call(
                ["cmd", "/c", "mklink", "/J", str(current), str(new_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except subprocess.CalledProcessError as e:
            _log(f"mklink failed: {e!r}")
            return False
    else:
        try:
            current.symlink_to(new_dir, target_is_directory=True)
            return True
        except Exception as e:  # noqa: BLE001
            _log(f"symlink failed: {e!r}")
            return False


def _relaunch_via_bat(install_root: Path) -> None:
    bat = install_root / "run-agent.bat"
    if not bat.exists():
        _log(f"run-agent.bat not found at {bat}; not relaunching")
        return
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008  # DETACHED_PROCESS
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=creationflags)
    os._exit(0)  # current agent exits; new one takes over


def install_update(release: dict, install_root: Path) -> bool:
    tag = release.get("tag_name", "")
    url = _asset_url(release)
    if not url:
        _log(f"release {tag!r} has no {ASSET_NAME}")
        return False
    new_dir = install_root / f"cams-agent-{tag}"
    if new_dir.exists():
        _log(f"directory already exists: {new_dir}; skipping download")
    else:
        tmp_zip = install_root / f"download-{tag}.zip"
        _log(f"downloading {url}")
        if not _download_zip(url, tmp_zip):
            return False
        _log("extracting…")
        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                zf.extractall(new_dir)
        except Exception as e:  # noqa: BLE001
            _log(f"extract failed: {e!r}")
            return False
        try:
            tmp_zip.unlink()
        except OSError:
            pass
    if not _swap_current(install_root, new_dir):
        return False
    _log(f"updated to {tag}; relaunching")
    _relaunch_via_bat(install_root)
    return True


def check_and_update(current_version: str) -> tuple[bool, str]:
    """Returns (updated, message). Skips if dev/source mode or no install_root."""
    if not _is_frozen():
        return False, "dev mode (not frozen)"
    install_root = _install_root()
    if install_root is None:
        return False, "no install root"
    release = fetch_latest_release()
    if release is None:
        return False, "github unreachable"
    latest = release.get("tag_name", "")
    if _parse_version(latest) <= _parse_version(current_version):
        return False, f"already on latest ({current_version} >= {latest})"
    _log(f"new release: {latest} (current {current_version})")
    if install_update(release, install_root):
        return True, f"updated to {latest}"
    return False, "install failed"


def background_check_loop(current_version: str, on_status: Callable[[str], None] | None = None) -> threading.Thread:
    """Spawns a daemon thread that polls GitHub every hour. on_status is
    called with a one-line description after every attempt (useful for tray
    status updates)."""

    def _loop() -> None:
        while True:
            try:
                updated, msg = check_and_update(current_version)
                if on_status is not None:
                    on_status(msg)
                if updated:
                    return  # we're about to be killed anyway
            except Exception as e:  # noqa: BLE001
                _log(f"loop error: {e!r}")
            time.sleep(CHECK_INTERVAL_SECONDS)

    t = threading.Thread(target=_loop, daemon=True, name="updater")
    t.start()
    return t
