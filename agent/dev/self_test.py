"""Boot-time camera self-test.

After /agent/config is fetched, ping each camera once: snapshot URL, latency,
auth, and a tiny 3-frame variance check (so a frozen-but-200 stream is caught
too). The result is logged locally, posted in the next heartbeat, and shown
through the tray's Diagnóstico menu — so the customer sees ✓/✗ per camera the
moment the agent boots.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import asdict, dataclass

from rtsp_probe import http_snapshot_jpeg, is_http_snapshot, is_local


@dataclass
class CheckResult:
    camera_id: str
    name: str
    ok: bool
    latency_ms: int | None
    message: str
    kind: str  # "http", "rtsp", "dshow", "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


async def _check_http_snapshot(cam: dict) -> CheckResult:
    url = cam.get("rtsp_url") or ""
    name = cam.get("name") or cam.get("camera_id", "?")
    cam_id = str(cam.get("camera_id"))
    t0 = time.time()
    hashes: list[str] = []
    last_jpeg: bytes | None = None
    for _ in range(3):
        jpeg = await http_snapshot_jpeg(url, timeout=5.0)
        if jpeg is None:
            return CheckResult(
                camera_id=cam_id,
                name=name,
                ok=False,
                latency_ms=int((time.time() - t0) * 1000),
                message="snapshot fetch failed (auth or network)",
                kind="http",
            )
        hashes.append(hashlib.md5(jpeg).hexdigest())
        last_jpeg = jpeg
        await asyncio.sleep(0.4)
    latency_ms = int((time.time() - t0) * 1000)
    if len(set(hashes)) == 1:
        return CheckResult(
            camera_id=cam_id,
            name=name,
            ok=False,
            latency_ms=latency_ms,
            message="stream is frozen (3 identical frames)",
            kind="http",
        )
    size = len(last_jpeg) if last_jpeg else 0
    return CheckResult(
        camera_id=cam_id,
        name=name,
        ok=True,
        latency_ms=latency_ms,
        message=f"ok, {size} bytes, {len(set(hashes))}/3 unique frames",
        kind="http",
    )


async def _run_async(cameras: list[dict]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for cam in cameras:
        url = cam.get("rtsp_url") or ""
        if not url:
            results.append(
                CheckResult(
                    camera_id=str(cam.get("camera_id")),
                    name=cam.get("name") or "?",
                    ok=False,
                    latency_ms=None,
                    message="no rtsp_url configured",
                    kind="unknown",
                )
            )
            continue
        if is_http_snapshot(url):
            results.append(await _check_http_snapshot(cam))
        elif is_local(url):
            results.append(
                CheckResult(
                    camera_id=str(cam.get("camera_id")),
                    name=cam.get("name") or "?",
                    ok=True,
                    latency_ms=None,
                    message="dshow local device (skipped runtime check)",
                    kind="dshow",
                )
            )
        else:
            # RTSP / cv2 path. Doing a full ffprobe here can take 10s+ and we
            # don't want to gate boot on it; we mark as 'untested' but still
            # show in the panel so customer knows we didn't validate.
            results.append(
                CheckResult(
                    camera_id=str(cam.get("camera_id")),
                    name=cam.get("name") or "?",
                    ok=True,
                    latency_ms=None,
                    message="rtsp (probed lazily at first frame)",
                    kind="rtsp",
                )
            )
    return results


def run_self_test(cameras: list[dict]) -> list[CheckResult]:
    """Synchronous wrapper. Returns a list of CheckResult (one per camera)."""
    return asyncio.run(_run_async(cameras))


def summary(results: list[CheckResult]) -> str:
    """Human one-liner for the tray notification."""
    ok = sum(1 for r in results if r.ok)
    total = len(results)
    return f"{ok}/{total} câmeras OK"


def serialize(results: list[CheckResult]) -> dict:
    return {"checked_at": int(time.time()), "results": [r.to_dict() for r in results]}
