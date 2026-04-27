"""Dev-only stub agent.

Loop: read RTSP -> compute frame diff -> on motion record N seconds ->
request signed S3 PUT URL from API -> upload clip -> POST /events.
Heartbeat every 30s.

NOT production. Real agent will be Go + gocv. This exists so we can smoke-test
the cloud pipeline against a real IP camera.
"""

from __future__ import annotations

import argparse
import os
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
            payload = {
                "cameras_status": {cfg.camera_id: True},
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
    tmp = Path(tempfile.mkstemp(suffix=".mp4")[1])
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(tmp), fourcc, fps, size)
    target_frames = int(fps * seconds)
    written = 0
    while written < target_frames:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        written += 1
    writer.release()
    return tmp


def motion_score(prev_gray: np.ndarray, gray: np.ndarray) -> float:
    diff = cv2.absdiff(prev_gray, gray)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    return float(thresh.mean()) / 255.0


def run(cfg: AgentConfig) -> None:
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
    missing = [k for k in ("device_token", "rtsp", "camera_id") if not getattr(args, k)]
    if missing:
        p.error(f"missing required args: {missing}")
    return args


if __name__ == "__main__":
    run(AgentConfig(parse_args()))
