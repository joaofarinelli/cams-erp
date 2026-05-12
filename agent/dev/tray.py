"""Windows tray wrapper for the cams-erp agent.

Boot flow on every launch:

  1. Redirect stdio -> %LOCALAPPDATA%\\cams-agent\\agent.log
  2. Load config from %LOCALAPPDATA%\\cams-agent\\config.json
     (or auto-migrate from legacy CAMS_DEVICE_TOKEN env if present)
  3. If still no token, open the Tkinter pairing window — blocks until the
     user pairs or closes
  4. Spawn the agent CameraWorkerPool in a background thread
  5. Show the tray icon with menu (Status / Open logs / Run at startup /
     Reset pairing / Exit)

The agent itself learns its camera list, zones, and edge_yolo toggle from
/agent/config — the local file only persists the API URL + device token.
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
from agent import AgentConfig, build_config_from_disk, parse_args
from config_store import clear_config, config_dir, load_config


APP_NAME = "cams-agent"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _log_path() -> Path:
    return config_dir() / "agent.log"


def _redirect_stdio() -> None:
    f = open(_log_path(), "a", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = f
    sys.stderr = f


def _exe_command() -> str:
    """Path used by the HKCU\\Run autostart entry. The exe is always
    self-sufficient now (config.json carries the token), so we point the
    registry key straight at the binary."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except (FileNotFoundError, OSError):
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


def _ensure_paired() -> AgentConfig | None:
    """Try to load a config; if none, pop the pairing GUI and try again.
    Returns None only if the user dismissed the pairing dialog."""
    args = parse_args()
    cfg = build_config_from_disk(args)
    if cfg is not None:
        return cfg

    # No token in env, file, or CLI flag -> show pairing window.
    try:
        from pairing_gui import run_pairing_window

        saved = run_pairing_window()
    except Exception as e:  # noqa: BLE001
        agent.log(f"pairing window failed: {e!r}")
        return None

    if not saved:
        return None
    return build_config_from_disk(args)


_agent_thread_handle: threading.Thread | None = None


def _start_agent(cfg: AgentConfig) -> None:
    global _agent_thread_handle

    def _runner() -> None:
        try:
            agent.run(cfg)
        except SystemExit:
            pass
        except Exception as e:  # noqa: BLE001
            agent.log(f"agent thread crashed: {e!r}")

    t = threading.Thread(target=_runner, daemon=True, name="agent-main")
    t.start()
    _agent_thread_handle = t


def main() -> None:
    if sys.platform == "win32":
        _redirect_stdio()

    cfg = _ensure_paired()
    if cfg is None:
        agent.log("no pairing completed; exiting")
        sys.exit(0)

    _start_agent(cfg)

    def on_open_logs(_icon, _item):  # noqa: ANN001
        webbrowser.open(str(_log_path()))

    def on_check_update(_icon, _item):  # noqa: ANN001
        import updater
        from agent import AGENT_VERSION

        updated, msg = updater.check_and_update(AGENT_VERSION)
        icon.notify(msg, title="cams-agent — atualização")

    def on_diagnose(_icon, _item):  # noqa: ANN001
        st = cfg.last_self_test or {}
        results = st.get("results") or []
        if not results:
            icon.notify("Diagnóstico ainda não rodou. Aguarde o boot terminar.", title="cams-agent")
            return
        ok = sum(1 for r in results if r.get("ok"))
        lines = [f"{ok}/{len(results)} câmeras OK", ""]
        for r in results[:6]:
            mark = "✓" if r.get("ok") else "✗"
            lines.append(f"{mark} {r.get('name')}: {r.get('message')}")
        icon.notify("\n".join(lines), title="Diagnóstico")

    def on_status(_icon, _item):  # noqa: ANN001
        stored = load_config()
        msg = (
            f"API: {cfg.api_base}\n"
            f"Device: {cfg.device_name or stored.get('device_id', '(unknown)')}\n"
            f"Cameras: {len(cfg.cameras)} configured\n"
            f"Edge YOLO: {'on' if cfg.edge_yolo_enabled else 'off'}"
        )
        icon.notify(msg, title="cams-agent")

    def on_toggle_autostart(_icon, item):  # noqa: ANN001
        set_autostart(not item.checked)
        icon.update_menu()

    def on_reset(_icon, _item):  # noqa: ANN001
        clear_config()
        icon.notify("Pareamento removido. Reabra o app para parear de novo.", title="cams-agent")
        os._exit(0)

    def on_exit(_icon, _item):  # noqa: ANN001
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        APP_NAME,
        _make_icon_image(),
        APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Status", on_status, default=True),
            pystray.MenuItem("Diagnóstico", on_diagnose),
            pystray.MenuItem("Verificar atualização", on_check_update),
            pystray.MenuItem("Open logs", on_open_logs),
            pystray.MenuItem(
                "Run at startup",
                on_toggle_autostart,
                checked=lambda _i: autostart_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Reset pairing", on_reset),
            pystray.MenuItem("Exit", on_exit),
        ),
    )

    if sys.platform == "win32" and not autostart_enabled():
        set_autostart(True)

    icon.run()


if __name__ == "__main__":
    main()
