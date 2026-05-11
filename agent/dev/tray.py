"""Windows tray wrapper for the cams-erp agent.

Runs the agent loop in a background thread and shows a system-tray icon with
a context menu (Status / Open logs / Enable/disable autostart / Exit).

Console output is redirected to %LOCALAPPDATA%\\cams-agent\\agent.log so the
windowed exe (console=False) still leaves a debuggable trail.

Autostart uses HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run — no
admin rights required, per-user scope.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw
import pystray

import agent
from agent import AgentConfig, parse_args


APP_NAME = "cams-agent"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p / "agent.log"


def _redirect_stdio() -> None:
    """Send stdout/stderr to a rolling log file so the windowed exe is debuggable."""
    log_file = _log_path()
    f = open(log_file, "a", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = f
    sys.stderr = f


def _exe_command() -> str:
    """Path used by the Run registry key. Prefer the launcher .bat so env vars
    set there (API URL, device token) survive autostart. Falls back to the exe."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        bat = exe.parent.parent / "run-agent.bat"
        if bat.exists():
            return f'"{bat}"'
        return f'"{exe}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enable: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _exe_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


def _make_icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(20, 25, 40))
    d = ImageDraw.Draw(img)
    d.rectangle((14, 22, 44, 46), outline=(180, 220, 255), width=3)
    d.polygon([(44, 26), (56, 18), (56, 50), (44, 42)], fill=(180, 220, 255))
    d.ellipse((28, 30, 34, 36), fill=(220, 80, 80))
    return img


def _agent_thread(cfg: AgentConfig) -> None:
    try:
        agent.run(cfg)
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001
        agent.log(f"agent thread crashed: {e!r}")


def main() -> None:
    if sys.platform == "win32":
        _redirect_stdio()

    cfg: AgentConfig | None = None
    try:
        cfg = AgentConfig(parse_args())
    except SystemExit:
        agent.log("missing device token; tray will idle until configured")

    if cfg is not None:
        t = threading.Thread(target=_agent_thread, args=(cfg,), daemon=True)
        t.start()

    def on_open_logs(_icon, _item):  # noqa: ANN001
        webbrowser.open(str(_log_path()))

    def on_status(_icon, _item):  # noqa: ANN001
        if cfg is None:
            icon.notify("No device token configured.", title="cams-agent")
        else:
            icon.notify(
                f"API: {cfg.api_base}\nCamera: {cfg.camera_id or '(none)'}",
                title="cams-agent",
            )

    def on_toggle_autostart(_icon, item):  # noqa: ANN001
        set_autostart(not item.checked)
        icon.update_menu()

    def on_exit(_icon, _item):  # noqa: ANN001
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        APP_NAME,
        _make_icon_image(),
        APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Status", on_status, default=True),
            pystray.MenuItem("Open logs", on_open_logs),
            pystray.MenuItem(
                "Run at startup",
                on_toggle_autostart,
                checked=lambda _i: autostart_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit),
        ),
    )

    if sys.platform == "win32" and not autostart_enabled():
        set_autostart(True)

    icon.run()


if __name__ == "__main__":
    main()
