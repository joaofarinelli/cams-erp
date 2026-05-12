"""Per-camera JPEG ring buffer on local disk.

For each camera we keep ~24h of motion-captured JPEGs at the agent's
poll cadence (~2 fps) so the cloud can request "give me 30s before the
alert" after the fact, without keeping every camera streaming to S3.

Layout:
    %LOCALAPPDATA%\\cams-agent\\buffer\\{camera_id}\\{hourly_bucket}.jsonl
        each line = {"ts": float, "jpeg_b64": str}
    Hourly buckets are pruned automatically when total bytes exceed
    `max_bytes`. JSONL keeps random access simple (one line per frame
    = one binary search-friendly entry).

This is intentionally low-tech (no ffmpeg muxing for the buffer itself):
    * JSON line per frame survives partial writes
    * Easy to slice by ts without seeking through a video container
    * ffmpeg muxes the slice into MP4 only when a `seek_clip` job arrives
"""

from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
from pathlib import Path

from config_store import config_dir


def buffer_root() -> Path:
    p = config_dir() / "buffer"
    p.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(p, 0o700)
    return p


def _bucket_path(camera_id: str, ts: float) -> Path:
    h = int(ts // 3600)
    d = buffer_root() / camera_id
    d.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(d, 0o700)
    return d / f"{h}.jsonl"


class RingBuffer:
    """One-per-camera writer. Thread-safe writes; readers don't lock — the
    bucket files are append-only until pruned, so readers just enumerate
    files older than `max_age_s` and drop them."""

    def __init__(
        self,
        camera_id: str,
        *,
        max_age_s: int = 24 * 3600,
        max_bytes: int = 256 * 1024 * 1024,  # 256MB/cam default
    ) -> None:
        self.camera_id = camera_id
        self.max_age_s = max_age_s
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._last_prune = 0.0

    def write(self, jpeg: bytes, ts: float | None = None) -> None:
        if not jpeg:
            return
        if ts is None:
            ts = time.time()
        path = _bucket_path(self.camera_id, ts)
        line = json.dumps({"ts": ts, "jpeg_b64": base64.b64encode(jpeg).decode("ascii")})
        with self._lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            if sys.platform != "win32":
                os.chmod(path, 0o600)
            if time.time() - self._last_prune > 60:
                self._prune()
                self._last_prune = time.time()

    def slice(self, from_ts: float, to_ts: float) -> list[tuple[float, bytes]]:
        """Returns frames in [from_ts, to_ts] in chronological order."""
        out: list[tuple[float, bytes]] = []
        h_from = int(from_ts // 3600)
        h_to = int(to_ts // 3600)
        for h in range(h_from, h_to + 1):
            p = buffer_root() / self.camera_id / f"{h}.jsonl"
            if not p.exists():
                continue
            try:
                with p.open("r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        ts = obj.get("ts")
                        if ts is None:
                            continue
                        if from_ts <= ts <= to_ts:
                            try:
                                jpeg = base64.b64decode(obj["jpeg_b64"])
                            except Exception:  # noqa: BLE001
                                continue
                            out.append((ts, jpeg))
            except OSError:
                continue
        out.sort(key=lambda t: t[0])
        return out

    def _prune(self) -> None:
        """Drop bucket files older than max_age_s; if total still over budget,
        drop oldest until under. Cheap because buckets are roughly equal-sized."""
        root = buffer_root() / self.camera_id
        if not root.exists():
            return
        now = time.time()
        files = sorted(root.glob("*.jsonl"))
        # First pass: age-based prune.
        for f in files:
            try:
                hour = int(f.stem)
            except ValueError:
                continue
            if (now - (hour + 1) * 3600) > self.max_age_s:
                try:
                    f.unlink()
                except OSError:
                    pass
        # Second pass: size-based prune.
        files = sorted(root.glob("*.jsonl"))
        total = sum(f.stat().st_size for f in files if f.exists())
        while total > self.max_bytes and files:
            oldest = files.pop(0)
            try:
                sz = oldest.stat().st_size
                oldest.unlink()
                total -= sz
            except OSError:
                break
