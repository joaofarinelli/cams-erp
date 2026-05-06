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
from rtsp_probe import first_frame_jpeg, jpeg_to_data_url, probe_stream


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class AgentConfig:
    def __init__(self, args: argparse.Namespace) -> None:
        self.api_base = args.api.rstrip("/")
        self.device_token = args.device_token
        self.rtsp_url = args.rtsp
        self.camera_id = args.camera_id
        self.clip_seconds = args.clip_seconds
        self.motion_threshold = args.motion_threshold
        self.cooldown = args.cooldown
        self.heartbeat_interval = args.heartbeat


def heartbeat_loop(cfg: AgentConfig, stop: threading.Event) -> None:
    headers = {"X-Device-Token": cfg.device_token}
    while not stop.is_set():
        try:
            cameras_status = {cfg.camera_id: True} if cfg.camera_id else {}
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
        except Exception as e:
            log(f"heartbeat error: {e}")
        stop.wait(cfg.heartbeat_interval)


def request_upload_url(cfg: AgentConfig, started_at: datetime, duration_ms: int) -> dict[str, Any]:
    r = httpx.post(
        f"{cfg.api_base}/clips/upload-url",
        json={
            "camera_id": cfg.camera_id,
            "started_at": started_at.isoformat(),
            "duration_ms": duration_ms,
        },
        headers={"X-Device-Token": cfg.device_token},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def post_event(cfg: AgentConfig, s3_key: str, motion_score: float, started_at: datetime, duration_ms: int) -> dict[str, Any]:
    r = httpx.post(
        f"{cfg.api_base}/events",
        json={
            "camera_id": cfg.camera_id,
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
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
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
    try:
        if type_ == "snapshot":
            rtsp = params["rtsp_url"]
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
            await ws.send(
                json.dumps({"job_id": job_id, "ok": True, "result": {"devices": devices}})
            )
        elif type_ == "probe":
            rtsp = params["rtsp_url"]
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


async def _live_stream(ws, camera_id: str, rtsp_url: str) -> None:
    import base64

    log(f"live_start cam={camera_id}")
    args = [
        "ffmpeg",
        "-loglevel", "error",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-vf", "fps=24,scale=640:-2",
        "-c:v", "mjpeg",
        "-q:v", "7",
        "-f", "mjpeg",
        "pipe:1",
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
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


async def _start_live(ws, camera_id: str, rtsp_url: str) -> None:
    if camera_id in _LIVE_TASKS:
        return
    task = asyncio.create_task(_live_stream(ws, camera_id, rtsp_url))
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
                        asyncio.create_task(
                            _start_live(ws, msg["camera_id"], msg["rtsp_url"])
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


def run(cfg: AgentConfig) -> None:
    if not cfg.rtsp_url or not cfg.camera_id:
        log("control-only mode (no RTSP/camera) — heartbeat + onboarding jobs only")
        stop = threading.Event()
        hb = threading.Thread(target=heartbeat_loop, args=(cfg, stop), daemon=True)
        hb.start()
        ctl = threading.Thread(target=control_thread, args=(cfg, stop), daemon=True)
        ctl.start()
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            stop.set()
        return

    log(f"connecting RTSP: {cfg.rtsp_url}")
    cap = cv2.VideoCapture(cfg.rtsp_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        log("RTSP open failed")
        sys.exit(1)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    log(f"stream: {width}x{height} @ {fps:.1f}fps")

    stop = threading.Event()
    hb = threading.Thread(target=heartbeat_loop, args=(cfg, stop), daemon=True)
    hb.start()
    ctl = threading.Thread(target=control_thread, args=(cfg, stop), daemon=True)
    ctl.start()

    prev_gray: np.ndarray | None = None
    last_trigger_at = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                log("frame read failed; reconnecting in 2s")
                time.sleep(2)
                cap = cv2.VideoCapture(cfg.rtsp_url, cv2.CAP_FFMPEG)
                continue
            gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
            if prev_gray is None:
                prev_gray = gray
                continue
            score = motion_score(prev_gray, gray)
            prev_gray = gray
            now = time.time()
            if score >= cfg.motion_threshold and (now - last_trigger_at) >= cfg.cooldown:
                last_trigger_at = now
                log(f"motion {score:.3f} -> recording {cfg.clip_seconds}s")
                started_at = datetime.now(tz=timezone.utc)
                clip_path = record_clip(cap, fps, (width, height), cfg.clip_seconds)
                duration_ms = cfg.clip_seconds * 1000
                try:
                    res = request_upload_url(cfg, started_at, duration_ms)
                    log(f"upload-url ok: s3_key={res['s3_key']}")
                    upload_clip(res["upload_url"], clip_path)
                    log("clip uploaded")
                    ev = post_event(cfg, res["s3_key"], score, started_at, duration_ms)
                    log(f"event ack: id={ev['id']} enqueued={ev['enqueued']}")
                except httpx.HTTPError as e:
                    log(f"pipeline error: {e!r}")
                finally:
                    clip_path.unlink(missing_ok=True)
                    prev_gray = None
    except KeyboardInterrupt:
        log("stopping")
    finally:
        stop.set()
        cap.release()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("CAMS_API", "http://localhost:8000"))
    p.add_argument("--device-token", default=os.environ.get("CAMS_DEVICE_TOKEN", ""))
    p.add_argument("--rtsp", default=os.environ.get("CAMS_RTSP_URL", ""))
    p.add_argument("--camera-id", default=os.environ.get("CAMS_CAMERA_ID", ""))
    p.add_argument("--clip-seconds", type=int, default=5)
    p.add_argument("--motion-threshold", type=float, default=0.02)
    p.add_argument("--cooldown", type=int, default=15)
    p.add_argument("--heartbeat", type=int, default=30)
    args = p.parse_args()
    if not args.device_token:
        p.error("missing --device-token")
    return args


if __name__ == "__main__":
    run(AgentConfig(parse_args()))
