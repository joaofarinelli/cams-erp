"""Dev-only S3+SQS stub. Mounted only when CAMS_AUTH_BYPASS=1.

PUT /dev/s3/{path}      writes body to /tmp/cams-erp-clips/<path>
GET /dev/s3/{path}      serves saved clip
GET /dev/events         tails /tmp/cams-erp-events.log (jsonl)

Production uses real S3 (signed URL) and SQS. This destrava end-to-end smoke
testing without moto/localstack.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

CLIPS_DIR = Path("/tmp/cams-erp-clips")
EVENTS_LOG = Path("/tmp/cams-erp-events.log")
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/dev", tags=["dev"])


@router.put("/s3/{path:path}")
async def put_clip(path: str, request: Request) -> JSONResponse:
    body = await request.body()
    target = CLIPS_DIR / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return JSONResponse({"ok": True, "path": str(target), "bytes": len(body)})


@router.get("/s3/{path:path}")
async def get_clip(path: str) -> FileResponse:
    return FileResponse(CLIPS_DIR / path, media_type="video/mp4")


@router.get("/events")
async def tail_events() -> PlainTextResponse:
    if not EVENTS_LOG.exists():
        return PlainTextResponse("")
    return PlainTextResponse(EVENTS_LOG.read_text())


def append_event(payload: dict) -> None:
    EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_LOG.open("a") as f:
        f.write(json.dumps(payload) + "\n")
