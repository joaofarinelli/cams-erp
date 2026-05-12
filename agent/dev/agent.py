"""Dev-only stub agent.

Loop: read RTSP -> compute frame diff -> on motion record N seconds ->
request signed S3 PUT URL from API -> upload clip -> POST /events.
Heartbeat every 30s.

NOT production. Real agent will be Go + gocv. This exists so we can smoke-test
the cloud pipeline against a real IP camera.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
import websockets

from discovery import url_templates_for, ws_discover
from rtsp_probe import (
    first_frame_jpeg,
    http_snapshot_jpeg,
    is_http_snapshot,
    is_local,
    jpeg_to_data_url,
    list_dshow_devices,
    probe_stream,
)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# Suppress the console window that subprocess.Popen opens on Windows when the
# parent is a GUI app (PyInstaller console=False). Without this, every ffmpeg
# spawn flashes a CMD window.
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _edge_yolo_passes(cfg: "AgentConfig", camera_id: str, frame: np.ndarray) -> bool:
    """Gate at motion-trigger time. Returns True if upload should proceed.

    False when edge YOLO is enabled (per-device flag from /agent/config) AND
    no person is detected inside the camera's rule zones. Logs either way
    for observability. Degrades open: missing onnxruntime, missing weights,
    or an invalid frame all return True (no silent drops)."""
    if not cfg.edge_yolo_enabled or frame is None:
        return True
    from edge_yolo import get_edge_yolo

    yolo = get_edge_yolo(cfg.edge_yolo_conf)
    if yolo is None:
        return True
    zones = cfg.camera_zones.get(str(camera_id), {})
    in_zone, max_conf = yolo.person_in_zone(frame, zones)
    if in_zone:
        log(f"[edge] cam={camera_id[:8]} person in zone conf={max_conf:.2f} -> upload")
        return True
    log(f"[edge] cam={camera_id[:8]} no person in zone (max_conf={max_conf:.2f}) -> skip")
    return False


class AgentConfig:
    """Runtime config for the agent.

    Camera list, zones, and the edge_yolo toggle are all owned by the cloud
    (web panel writes them; agent fetches via /agent/config). The local
    config.json only persists the API URL + device token so the agent can
    connect on boot."""

    def __init__(
        self,
        *,
        api_base: str,
        device_token: str,
        clip_seconds: int = 5,
        motion_threshold: float = 0.02,
        cooldown: int = 15,
        heartbeat_interval: int = 30,
        edge_yolo_conf: float = 0.35,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.device_token = device_token
        self.clip_seconds = clip_seconds
        self.motion_threshold = motion_threshold
        self.cooldown = cooldown
        self.heartbeat_interval = heartbeat_interval
        self.edge_yolo_conf = edge_yolo_conf
        # Pushed by /agent/config refresh:
        self.edge_yolo_enabled: bool = False
        self.camera_zones: dict[str, dict] = {}  # camera_id -> merged zones
        self.cameras: list[dict] = []  # latest [{camera_id, name, rtsp_url, rules}, ...]
        self.config_etag: str | None = None
        self.device_name: str | None = None


def refresh_agent_config(cfg: AgentConfig) -> bool:
    """Pull /agent/config and populate cfg.cameras / cfg.camera_zones /
    cfg.edge_yolo_enabled / cfg.device_name. Returns True iff the etag changed
    (i.e. the worker pool needs to resync)."""
    try:
        r = httpx.get(
            f"{cfg.api_base}/agent/config",
            headers={"X-Device-Token": cfg.device_token},
            timeout=10,
        )
        if r.status_code != 200:
            log(f"config refresh: HTTP {r.status_code}")
            return False
        data = r.json()
    except Exception as e:  # noqa: BLE001
        log(f"config refresh error: {e!r}")
        return False

    etag = data.get("etag")
    cameras = data.get("cameras") or []
    new_zones: dict[str, dict] = {}
    for cam in cameras:
        merged: dict = {}
        for rule in cam.get("rules") or []:
            for name, pts in (rule.get("zones") or {}).items():
                merged[name] = pts
        new_zones[str(cam.get("camera_id"))] = merged

    cfg.cameras = cameras
    cfg.camera_zones = new_zones
    cfg.edge_yolo_enabled = bool(data.get("edge_yolo_enabled", False))
    cfg.device_name = data.get("device_name")
    changed = etag != cfg.config_etag
    cfg.config_etag = etag
    return changed


def heartbeat_loop(
    cfg: AgentConfig,
    stop: threading.Event,
    pool: "CameraWorkerPool | None" = None,
) -> None:
    """Heartbeat the API every cfg.heartbeat_interval seconds. When the cloud
    signals a new config_etag, trigger a full refresh + pool resync."""
    headers = {"X-Device-Token": cfg.device_token}
    last_etag: str | None = None
    while not stop.is_set():
        try:
            cameras_status = pool.health_snapshot() if pool is not None else {}
            payload = {
                "cameras_status": cameras_status,
                "cpu_pct": 0.0,
                "ram_mb": 0,
                "disk_free_mb": 0,
                "agent_version": "dev-stub",
            }
            r = httpx.post(
                f"{cfg.api_base}/agent/heartbeat", json=payload, headers=headers, timeout=10
            )
            log(f"heartbeat -> {r.status_code}")
            if r.status_code == 200:
                etag = r.json().get("config_etag")
                if etag != last_etag and pool is not None:
                    if refresh_agent_config(cfg):
                        pool.sync(cfg.cameras)
                    last_etag = etag
        except Exception as e:
            log(f"heartbeat error: {e}")
        stop.wait(cfg.heartbeat_interval)


def request_upload_url(
    cfg: AgentConfig, camera_id: str, started_at: datetime, duration_ms: int
) -> dict[str, Any]:
    r = httpx.post(
        f"{cfg.api_base}/clips/upload-url",
        json={
            "camera_id": camera_id,
            "started_at": started_at.isoformat(),
            "duration_ms": duration_ms,
        },
        headers={"X-Device-Token": cfg.device_token},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def post_event(
    cfg: AgentConfig,
    camera_id: str,
    s3_key: str,
    motion_score: float,
    started_at: datetime,
    duration_ms: int,
) -> dict[str, Any]:
    r = httpx.post(
        f"{cfg.api_base}/events",
        json={
            "camera_id": camera_id,
            "s3_key": s3_key,
            "motion_score": motion_score,
            "started_at": started_at.isoformat(),
            "duration_ms": duration_ms,
        },
        headers={"X-Device-Token": cfg.device_token},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def upload_clip(upload_url: str, path: Path) -> None:
    with path.open("rb") as f:
        r = httpx.put(upload_url, content=f.read(), headers={"Content-Type": "video/mp4"}, timeout=60)
    r.raise_for_status()


def record_clip(cap: cv2.VideoCapture, fps: float, size: tuple[int, int], seconds: int) -> Path:
    """Pipe raw BGR frames into ffmpeg, encode H.264 with +faststart so the
    resulting MP4 plays natively in <video> tags (browsers reject mp4v)."""
    tmp = Path(tempfile.mkstemp(suffix=".mp4")[1])
    width, height = size
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}",
        "-r", f"{fps:.2f}",
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(tmp),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=_SUBPROCESS_FLAGS)
    assert proc.stdin is not None
    target_frames = int(fps * seconds)
    written = 0
    try:
        while written < target_frames:
            ok, frame = cap.read()
            if not ok:
                break
            proc.stdin.write(frame.tobytes())
            written += 1
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)
    return tmp


def motion_score(prev_gray: np.ndarray, gray: np.ndarray) -> float:
    diff = cv2.absdiff(prev_gray, gray)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    return float(thresh.mean()) / 255.0


async def _handle_job(ws, msg: dict[str, Any]) -> None:
    import base64

    job_id = msg.get("job_id")
    type_ = msg.get("type")
    params = msg.get("params") or {}

    def _source(p: dict) -> str:
        return p.get("source") or p.get("rtsp_url") or ""

    try:
        if type_ == "snapshot":
            rtsp = _source(params)
            jpeg = await first_frame_jpeg(rtsp, timeout=8.0)
            if jpeg is None:
                await ws.send(
                    json.dumps({"job_id": job_id, "ok": False, "error": "ffmpeg_failed"})
                )
                return
            await ws.send(
                json.dumps(
                    {
                        "job_id": job_id,
                        "ok": True,
                        "result": {"jpeg_b64": base64.b64encode(jpeg).decode()},
                    }
                )
            )
        elif type_ == "discover":
            raw = await ws_discover(timeout=float(params.get("timeout", 3.0)))
            devices = []
            for d in raw:
                if not d.get("ip"):
                    continue
                d2 = {**d, "url_templates": url_templates_for(d.get("vendor"))}
                devices.append(d2)
            local = await list_dshow_devices()
            await ws.send(
                json.dumps(
                    {
                        "job_id": job_id,
                        "ok": True,
                        "result": {"devices": devices, "local_devices": local},
                    }
                )
            )
        elif type_ == "list_local":
            local = await list_dshow_devices()
            await ws.send(
                json.dumps({"job_id": job_id, "ok": True, "result": {"local_devices": local}})
            )
        elif type_ == "logs":
            # Return tail of agent.log. Used by the web panel to debug a
            # remote agent without asking the customer to copy/paste.
            from config_store import config_dir

            tail = int(params.get("tail") or 200)
            tail = max(1, min(tail, 2000))
            log_path = config_dir() / "agent.log"
            try:
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()[-tail:]
                content = "".join(lines)
            except FileNotFoundError:
                content = ""
            except Exception as e:  # noqa: BLE001
                content = f"[error reading log: {e!r}]"
            await ws.send(
                json.dumps(
                    {
                        "job_id": job_id,
                        "ok": True,
                        "result": {"path": str(log_path), "content": content, "lines": len(content.splitlines())},
                    }
                )
            )
        elif type_ == "probe":
            rtsp = _source(params)
            info = await probe_stream(rtsp, timeout=8.0)
            preview = None
            if info.get("ok") and params.get("include_frame", True):
                jpeg = await first_frame_jpeg(rtsp, timeout=8.0)
                if jpeg is not None:
                    preview = jpeg_to_data_url(jpeg)
            await ws.send(
                json.dumps(
                    {
                        "job_id": job_id,
                        "ok": True,
                        "result": {**info, "preview_data_url": preview},
                    }
                )
            )
        else:
            await ws.send(
                json.dumps({"job_id": job_id, "ok": False, "error": f"unknown_type:{type_}"})
            )
    except Exception as e:  # noqa: BLE001
        await ws.send(json.dumps({"job_id": job_id, "ok": False, "error": repr(e)}))


_LIVE_TASKS: dict[str, asyncio.Task] = {}


async def _live_snapshot_loop(ws, camera_id: str, source: str, fps: float = 1.0) -> None:
    """Live view via HTTP snapshot polling. Used for DVRs with broken RTSP
    (e.g. Hikvision-clone firmware missing SPS/PPS in-band)."""
    import base64

    interval = max(0.1, 1.0 / fps)
    while True:
        jpeg = await http_snapshot_jpeg(source, timeout=5.0)
        if jpeg is None:
            await asyncio.sleep(interval)
            continue
        try:
            await ws.send(
                json.dumps(
                    {
                        "type": "frame",
                        "camera_id": camera_id,
                        "data": base64.b64encode(jpeg).decode(),
                    }
                )
            )
        except Exception as e:  # noqa: BLE001
            log(f"live send failed cam={camera_id}: {e!r}")
            return
        await asyncio.sleep(interval)


async def _live_stream(ws, camera_id: str, source: str) -> None:
    import base64

    log(f"live_start cam={camera_id} source={source[:50]}")
    if is_http_snapshot(source):
        await _live_snapshot_loop(ws, camera_id, source)
        return
    if is_local(source):
        rest = source.split(":", 1)[1]
        spec = rest if rest.startswith("video=") else f"video={rest}"
        input_args = ["-f", "dshow", "-i", spec]
    else:
        input_args = ["-rtsp_transport", "tcp", "-i", source]
    args = (
        ["ffmpeg", "-loglevel", "error"]
        + input_args
        + [
            "-vf", "fps=24,scale=640:-2",
            "-c:v", "mjpeg",
            "-q:v", "7",
            "-f", "mjpeg",
            "pipe:1",
        ]
    )
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=_SUBPROCESS_FLAGS,
    )
    buf = b""
    try:
        assert proc.stdout is not None
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            buf += chunk
            while True:
                soi = buf.find(b"\xff\xd8")
                if soi < 0:
                    buf = b""
                    break
                eoi = buf.find(b"\xff\xd9", soi + 2)
                if eoi < 0:
                    buf = buf[soi:]
                    break
                jpeg = buf[soi : eoi + 2]
                buf = buf[eoi + 2 :]
                try:
                    await ws.send(
                        json.dumps(
                            {
                                "type": "frame",
                                "camera_id": camera_id,
                                "data": base64.b64encode(jpeg).decode(),
                            }
                        )
                    )
                except Exception as e:  # noqa: BLE001
                    log(f"live send failed cam={camera_id}: {e!r}")
                    return
    finally:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        log(f"live_stop cam={camera_id}")


async def _start_live(ws, camera_id: str, source: str) -> None:
    if camera_id in _LIVE_TASKS:
        return
    task = asyncio.create_task(_live_stream(ws, camera_id, source))
    _LIVE_TASKS[camera_id] = task

    def _cleanup(_t: asyncio.Task) -> None:
        _LIVE_TASKS.pop(camera_id, None)

    task.add_done_callback(_cleanup)


def _stop_live(camera_id: str) -> None:
    task = _LIVE_TASKS.pop(camera_id, None)
    if task and not task.done():
        task.cancel()


async def _control_loop(api_base: str, device_token: str) -> None:
    ws_url = api_base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url += f"/agent/control?token={device_token}"
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                log("control WS connected")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    t = msg.get("type")
                    if t == "live_start":
                        src = msg.get("source") or msg.get("rtsp_url") or ""
                        asyncio.create_task(
                            _start_live(ws, msg["camera_id"], src)
                        )
                    elif t == "live_stop":
                        _stop_live(msg["camera_id"])
                    else:
                        asyncio.create_task(_handle_job(ws, msg))
        except Exception as e:  # noqa: BLE001
            log(f"control WS dropped ({e!r}); reconnecting in 5s")
            for cam_id in list(_LIVE_TASKS.keys()):
                _stop_live(cam_id)
            await asyncio.sleep(5)


def control_thread(cfg: AgentConfig, stop: threading.Event) -> None:
    """Run the asyncio control loop in its own thread alongside the cv2 loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(_control_loop(cfg.api_base, cfg.device_token))
    try:
        while not stop.is_set():
            loop.run_until_complete(asyncio.sleep(0.5))
    finally:
        task.cancel()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


class CameraWorker(threading.Thread):
    """Motion-trigger loop for one camera. Picks HTTP-snapshot vs cv2-RTSP
    based on the source URL. Owns its own state (prev_gray, cooldown timer)
    so multiple cameras run in isolation. Designed to be stop()'d cleanly
    when the camera is removed from /agent/config."""

    POLL_FPS_SNAPSHOT = 2.0

    def __init__(self, cfg: AgentConfig, camera: dict) -> None:
        super().__init__(daemon=True, name=f"cam-{camera['camera_id'][:8]}")
        self.cfg = cfg
        self.camera_id = str(camera["camera_id"])
        self.rtsp_url = camera.get("rtsp_url") or ""
        self.name_pretty = camera.get("name") or self.camera_id[:8]
        self._stop = threading.Event()
        self._healthy = False

    @property
    def healthy(self) -> bool:
        return self._healthy and self.is_alive()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # noqa: D401
        if not self.rtsp_url:
            log(f"[{self.name_pretty}] no source URL; worker exiting")
            return
        try:
            if is_http_snapshot(self.rtsp_url):
                self._run_http_snapshot()
            elif is_local(self.rtsp_url):
                log(f"[{self.name_pretty}] dshow source: motion loop not supported, idle")
                self._stop.wait()
            else:
                self._run_rtsp_cv2()
        except Exception as e:  # noqa: BLE001
            log(f"[{self.name_pretty}] worker crashed: {e!r}")
        finally:
            self._healthy = False

    # ----- HTTP snapshot path -----------------------------------------

    def _run_http_snapshot(self) -> None:
        interval = 1.0 / self.POLL_FPS_SNAPSHOT
        prev_gray: np.ndarray | None = None
        last_trigger_at = 0.0
        log(f"[{self.name_pretty}] http snapshot motion loop")
        self._healthy = True
        while not self._stop.is_set():
            loop_start = time.time()
            try:
                jpeg = asyncio.run(http_snapshot_jpeg(self.rtsp_url, timeout=5.0))
            except Exception as e:  # noqa: BLE001
                log(f"[{self.name_pretty}] snapshot fetch: {e!r}")
                jpeg = None
            if jpeg is None:
                self._stop.wait(interval)
                continue
            arr = np.frombuffer(jpeg, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                self._stop.wait(interval)
                continue
            gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
            if prev_gray is None:
                prev_gray = gray
            else:
                score = motion_score(prev_gray, gray)
                prev_gray = gray
                now = time.time()
                if score >= self.cfg.motion_threshold and (now - last_trigger_at) >= self.cfg.cooldown:
                    last_trigger_at = now
                    if not _edge_yolo_passes(self.cfg, self.camera_id, frame):
                        continue
                    self._handle_motion_snapshot(score)
                    prev_gray = None
            elapsed = time.time() - loop_start
            left = interval - elapsed
            if left > 0:
                self._stop.wait(left)

    def _handle_motion_snapshot(self, score: float) -> None:
        log(f"[{self.name_pretty}] motion {score:.3f} -> recording {self.cfg.clip_seconds}s")
        started_at = datetime.now(tz=timezone.utc)
        clip_path = self._record_snapshot_clip(self.POLL_FPS_SNAPSHOT)
        duration_ms = self.cfg.clip_seconds * 1000
        try:
            res = request_upload_url(self.cfg, self.camera_id, started_at, duration_ms)
            upload_clip(res["upload_url"], clip_path)
            ev = post_event(self.cfg, self.camera_id, res["s3_key"], score, started_at, duration_ms)
            log(f"[{self.name_pretty}] event ack: id={ev['id']} enqueued={ev['enqueued']}")
        except httpx.HTTPError as e:
            log(f"[{self.name_pretty}] pipeline error: {e!r}")
        finally:
            for _ in range(5):
                try:
                    clip_path.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.5)

    def _record_snapshot_clip(self, fps: float) -> Path:
        tmp = Path(tempfile.mkstemp(suffix=".mp4")[1])
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "image2pipe", "-framerate", f"{fps:.2f}", "-vcodec", "mjpeg",
            "-i", "-",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(tmp),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=_SUBPROCESS_FLAGS)
        assert proc.stdin is not None
        interval = 1.0 / fps
        target = int(fps * self.cfg.clip_seconds)
        written = 0
        try:
            while written < target and not self._stop.is_set():
                t0 = time.time()
                try:
                    jpeg = asyncio.run(http_snapshot_jpeg(self.rtsp_url, timeout=5.0))
                except Exception:  # noqa: BLE001
                    jpeg = None
                if jpeg is not None:
                    proc.stdin.write(jpeg)
                    written += 1
                elapsed = time.time() - t0
                if elapsed < interval:
                    time.sleep(interval - elapsed)
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
        return tmp

    # ----- RTSP cv2 path ----------------------------------------------

    def _run_rtsp_cv2(self) -> None:
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            log(f"[{self.name_pretty}] rtsp open failed")
            return
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        log(f"[{self.name_pretty}] rtsp {width}x{height} @ {fps:.1f}fps")
        prev_gray: np.ndarray | None = None
        last_trigger_at = 0.0
        self._healthy = True
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    log(f"[{self.name_pretty}] rtsp read failed; reconnect in 2s")
                    cap.release()
                    self._stop.wait(2)
                    if self._stop.is_set():
                        break
                    cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                    continue
                gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
                if prev_gray is None:
                    prev_gray = gray
                    continue
                score = motion_score(prev_gray, gray)
                prev_gray = gray
                now = time.time()
                if score >= self.cfg.motion_threshold and (now - last_trigger_at) >= self.cfg.cooldown:
                    last_trigger_at = now
                    if not _edge_yolo_passes(self.cfg, self.camera_id, frame):
                        continue
                    log(f"[{self.name_pretty}] motion {score:.3f} -> recording {self.cfg.clip_seconds}s")
                    started_at = datetime.now(tz=timezone.utc)
                    clip_path = record_clip(cap, fps, (width, height), self.cfg.clip_seconds)
                    duration_ms = self.cfg.clip_seconds * 1000
                    try:
                        res = request_upload_url(self.cfg, self.camera_id, started_at, duration_ms)
                        upload_clip(res["upload_url"], clip_path)
                        ev = post_event(self.cfg, self.camera_id, res["s3_key"], score, started_at, duration_ms)
                        log(f"[{self.name_pretty}] event ack: id={ev['id']} enqueued={ev['enqueued']}")
                    except httpx.HTTPError as e:
                        log(f"[{self.name_pretty}] pipeline error: {e!r}")
                    finally:
                        for _ in range(5):
                            try:
                                clip_path.unlink(missing_ok=True)
                                break
                            except PermissionError:
                                time.sleep(0.5)
                        prev_gray = None
        finally:
            cap.release()


class CameraWorkerPool:
    """Manages a CameraWorker per camera. Re-syncs from /agent/config when the
    cloud reports a new etag (web added/removed/edited cameras)."""

    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self._workers: dict[str, CameraWorker] = {}
        self._lock = threading.Lock()

    def sync(self, cameras: list[dict]) -> None:
        wanted_by_id = {str(c["camera_id"]): c for c in cameras if c.get("rtsp_url")}
        with self._lock:
            # Stop workers no longer in config or whose URL changed.
            for cid in list(self._workers.keys()):
                wanted = wanted_by_id.get(cid)
                if wanted is None or wanted.get("rtsp_url") != self._workers[cid].rtsp_url:
                    log(f"pool: stopping cam={cid[:8]} ({'removed' if wanted is None else 'url changed'})")
                    self._workers[cid].stop()
                    del self._workers[cid]
            # Spawn new workers.
            for cid, cam in wanted_by_id.items():
                if cid not in self._workers:
                    log(f"pool: starting cam={cid[:8]} ({cam.get('name')})")
                    w = CameraWorker(self.cfg, cam)
                    w.start()
                    self._workers[cid] = w

    def health_snapshot(self) -> dict[str, bool]:
        with self._lock:
            return {cid: w.healthy for cid, w in self._workers.items()}

    def stop_all(self) -> None:
        with self._lock:
            for w in self._workers.values():
                w.stop()
            self._workers.clear()


def run(cfg: AgentConfig) -> None:
    """Entry point. Spawns heartbeat + control WS + a CameraWorker per camera
    discovered via /agent/config. The pool auto-syncs on every etag change."""
    log(f"agent starting api={cfg.api_base}")
    refresh_agent_config(cfg)

    stop = threading.Event()
    pool = CameraWorkerPool(cfg)
    pool.sync(cfg.cameras)

    hb = threading.Thread(target=heartbeat_loop, args=(cfg, stop, pool), daemon=True)
    hb.start()
    ctl = threading.Thread(target=control_thread, args=(cfg, stop), daemon=True)
    ctl.start()
    try:
        while not stop.is_set():
            time.sleep(60)
    except KeyboardInterrupt:
        log("stopping")
    finally:
        stop.set()
        pool.stop_all()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("CAMS_API", ""))
    p.add_argument("--device-token", default=os.environ.get("CAMS_DEVICE_TOKEN", ""))
    p.add_argument("--clip-seconds", type=int, default=5)
    p.add_argument("--motion-threshold", type=float, default=0.02)
    p.add_argument("--cooldown", type=int, default=15)
    p.add_argument("--heartbeat", type=int, default=30)
    p.add_argument(
        "--edge-yolo-conf",
        type=float,
        default=float(os.environ.get("CAMS_EDGE_YOLO_CONF", "0.35")),
    )
    return p.parse_args()


def build_config_from_disk(args: argparse.Namespace | None = None) -> AgentConfig | None:
    """Pull api_base + device_token from %LOCALAPPDATA%\\cams-agent\\config.json,
    or auto-migrate from legacy env vars on first run. CLI flags (if provided)
    win over the file. Returns None when no token can be resolved — caller
    should launch the pairing GUI."""
    from config_store import auto_migrate_env, load_config, DEFAULT_API

    auto_migrate_env()  # idempotent
    stored = load_config()
    a = args or argparse.Namespace(
        api="",
        device_token="",
        clip_seconds=5,
        motion_threshold=0.02,
        cooldown=15,
        heartbeat=30,
        edge_yolo_conf=0.35,
    )
    api_base = (a.api or stored.get("api_base") or DEFAULT_API).rstrip("/")
    device_token = a.device_token or stored.get("device_token") or ""
    if not device_token:
        return None
    return AgentConfig(
        api_base=api_base,
        device_token=device_token,
        clip_seconds=a.clip_seconds,
        motion_threshold=a.motion_threshold,
        cooldown=a.cooldown,
        heartbeat_interval=a.heartbeat,
        edge_yolo_conf=a.edge_yolo_conf,
    )


if __name__ == "__main__":
    args = parse_args()
    cfg = build_config_from_disk(args)
    if cfg is None:
        sys.stderr.write(
            "No device token configured. Run the tray app (cams-agent.exe) "
            "to pair via GUI, or set CAMS_DEVICE_TOKEN.\n"
        )
        sys.exit(1)
    run(cfg)
