"""ffprobe + first-frame extraction. Runs on the agent (LAN-side).

Source URIs supported:
  - rtsp://...           IP cameras
  - http(s)://.../picture HTTP snapshot endpoint (e.g. Hikvision ISAPI)
  - dshow:N              Windows DirectShow device index (0,1,...)
  - dshow:video=<name>   Windows DirectShow device by name
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def is_local(source: str) -> bool:
    return source.startswith("dshow:")


def is_http_snapshot(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _split_http_auth(source: str) -> tuple[str, tuple[str, str] | None]:
    """Strip user:pass from URL. Returns (clean_url, (user, password) | None)."""
    parts = urlsplit(source)
    if not parts.username:
        return source, None
    user = parts.username
    pw = parts.password or ""
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    clean = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return clean, (user, pw)


async def http_snapshot_jpeg(source: str, timeout: float = 8.0) -> bytes | None:
    """Fetch a single JPEG from an HTTP snapshot endpoint. Tries digest first
    then falls back to basic auth, since most NVRs/DVRs use digest."""
    import httpx  # local import to keep ffmpeg-only paths cheap

    url, creds = _split_http_auth(source)
    auths: list[Any] = [None]
    if creds is not None:
        auths = [httpx.DigestAuth(*creds), httpx.BasicAuth(*creds)]
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for auth in auths:
                try:
                    r = await client.get(url, auth=auth)
                except httpx.HTTPError:
                    continue
                if r.status_code == 200 and r.content[:2] == b"\xff\xd8":
                    return r.content
    except Exception:
        return None
    return None


def _dshow_spec(source: str) -> str:
    """`dshow:0` -> `video=@device_pnp_0` style; we keep it simple and rely on
    `video=<n>` being interpreted as device index via dshow input plugin.

    For named devices we pass through: `dshow:video=Integrated Camera` ->
    `video=Integrated Camera`.
    """
    rest = source.split(":", 1)[1]
    if rest.startswith("video="):
        return rest
    # numeric index -> use list_devices output indexing trick: ffmpeg dshow
    # doesn't accept index directly, so caller resolves index -> name.
    # If we get here with a bare number it means the agent failed to resolve;
    # fall back to literal `video=<n>` (will likely fail).
    return f"video={rest}"


def _input_args(source: str, timeout_us: int | None = None) -> list[str]:
    if is_local(source):
        return ["-f", "dshow", "-i", _dshow_spec(source)]
    args: list[str] = ["-rtsp_transport", "tcp"]
    if timeout_us:
        args += ["-timeout", str(timeout_us)]
    args += ["-i", source]
    return args


async def list_dshow_devices(timeout: float = 3.0) -> list[dict[str, Any]]:
    """Enumerate Windows DirectShow video devices via ffmpeg.

    Returns list of {"name": str, "kind": "video"}. No-op on non-Windows.
    """
    if sys.platform != "win32":
        return []
    args = ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 2)
    except asyncio.TimeoutError:
        return []
    text = stderr.decode(errors="replace")
    devices: list[dict[str, Any]] = []
    in_video = False
    for line in text.splitlines():
        if "DirectShow video devices" in line:
            in_video = True
            continue
        if "DirectShow audio devices" in line:
            in_video = False
            continue
        if not in_video:
            continue
        m = re.search(r'"([^"]+)"', line)
        if m and "Alternative name" not in line:
            devices.append({"name": m.group(1), "kind": "video", "source": f"dshow:video={m.group(1)}"})
    return devices


async def probe_stream(source: str, timeout: float = 8.0) -> dict[str, Any]:
    if is_http_snapshot(source):
        jpeg = await http_snapshot_jpeg(source, timeout=timeout)
        if jpeg is None:
            return {"ok": False, "error": "http snapshot fetch failed"}
        try:
            import numpy as np  # type: ignore
            import cv2  # type: ignore

            arr = np.frombuffer(jpeg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
        except Exception:
            w, h = 0, 0
        return {"ok": True, "codec": "mjpeg", "width": w, "height": h, "fps": 0.0}
    if is_local(source):
        # ffprobe + dshow is fragile; do a one-frame extract instead and
        # synthesize stream info from the JPEG dimensions.
        jpeg = await first_frame_jpeg(source, timeout=timeout)
        if jpeg is None:
            return {"ok": False, "error": "could not capture frame from local device"}
        try:
            import numpy as np  # type: ignore
            import cv2  # type: ignore

            arr = np.frombuffer(jpeg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
        except Exception:
            w, h = 640, 480
        return {"ok": True, "codec": "mjpeg", "width": w, "height": h, "fps": 0.0}

    args = (
        ["ffprobe", "-v", "error"]
        + _input_args(source, timeout_us=int(timeout * 1_000_000))
        + ["-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate", "-of", "json"]
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 2)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout connecting to RTSP"}
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace")[:300].strip()
        return {"ok": False, "error": msg or "ffprobe failed"}
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "could not parse ffprobe output"}

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        return {"ok": False, "error": "no video stream in response"}
    fps_str = video.get("r_frame_rate", "0/0")
    try:
        num, den = fps_str.split("/")
        fps = round(float(num) / float(den), 1) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {
        "ok": True,
        "codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": fps,
    }


async def first_frame_jpeg(source: str, timeout: float = 8.0) -> bytes | None:
    if is_http_snapshot(source):
        return await http_snapshot_jpeg(source, timeout=timeout)
    args = (
        ["ffmpeg", "-loglevel", "error"]
        + _input_args(source, timeout_us=int(timeout * 1_000_000))
        + ["-frames:v", "1", "-vf", "scale=640:-2", "-f", "image2", "-c:v", "mjpeg", "-y", "pipe:1"]
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 2)
    except asyncio.TimeoutError:
        return None
    if proc.returncode != 0 or not stdout:
        return None
    return stdout


def jpeg_to_data_url(data: bytes) -> str:
    return "data:image/jpeg;base64," + base64.standard_b64encode(data).decode()
