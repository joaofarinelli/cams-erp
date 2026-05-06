"""ffprobe + first-frame extraction. Runs on the agent (LAN-side)."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any


async def probe_stream(rtsp_url: str, timeout: float = 8.0) -> dict[str, Any]:
    args = [
        "ffprobe",
        "-v", "error",
        "-rtsp_transport", "tcp",
        "-timeout", str(int(timeout * 1_000_000)),
        "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate",
        "-of", "json",
        rtsp_url,
    ]
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


async def first_frame_jpeg(rtsp_url: str, timeout: float = 8.0) -> bytes | None:
    args = [
        "ffmpeg",
        "-loglevel", "error",
        "-rtsp_transport", "tcp",
        "-timeout", str(int(timeout * 1_000_000)),
        "-i", rtsp_url,
        "-frames:v", "1",
        "-vf", "scale=640:-2",
        "-f", "image2",
        "-c:v", "mjpeg",
        "-y",
        "pipe:1",
    ]
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
