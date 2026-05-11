"""Production worker loop.

Polls the events table for unprocessed rows, downloads the clip from S3/R2,
runs the VLM, posts alerts to the API via X-Internal-Token. Marks events
as processed atomically with FOR UPDATE SKIP LOCKED so multiple workers
can run safely.
"""

from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import boto3
import httpx
import psycopg
from botocore.config import Config

from inference.vlm import score_clip


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _bool_env(name: str, default: bool = True) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _yolo_confidence_from_sensitivity(sensitivity: int | None) -> float:
    if sensitivity is None:
        return 0.35
    s = max(0, min(100, int(sensitivity)))
    return round(0.7 - (s / 100.0) * 0.6, 3)


def _is_active_now(schedule: dict | None) -> bool:
    if not schedule:
        return True
    from zoneinfo import ZoneInfo

    tz_name = schedule.get("timezone") or "America/Sao_Paulo"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    local = datetime.now(tz)
    weekday = local.weekday()
    cur = local.time()

    def _hhmm(s):
        from datetime import time as _t
        h, m = s.split(":")
        return _t(int(h), int(m))

    for w in schedule.get("windows") or []:
        days = w.get("days") or list(range(7))
        if weekday not in days:
            continue
        try:
            start = _hhmm(w["start"])
            end = _hhmm(w["end"])
        except (KeyError, ValueError):
            continue
        if start <= end and start <= cur <= end:
            return True
        if start > end and (cur >= start or cur <= end):
            return True
    return False


def _pg_dsn(url: str) -> str:
    """Strip SQLAlchemy driver prefix for psycopg."""
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["CAMS_AWS_ENDPOINT_URL"],
        region_name=os.environ.get("CAMS_AWS_REGION", "auto"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def _download_clip(s3, bucket: str, key: str) -> Path:
    fd, tmp = tempfile.mkstemp(suffix=".mp4", prefix="clip-")
    os.close(fd)
    s3.download_file(bucket, key, tmp)
    return Path(tmp)


def fetch_rules(conn, camera_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, enabled, zones, sensitivity, custom_prompt, schedule, analysis_intensity
            FROM rules WHERE camera_id = %s AND enabled = true
            """,
            (camera_id,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]


def claim_event(conn) -> dict | None:
    """Atomically claim one unprocessed event."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH claimed AS (
              SELECT id FROM events
              WHERE processed = false
              ORDER BY created_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1
            )
            UPDATE events SET processed = true
            WHERE id IN (SELECT id FROM claimed)
            RETURNING id, camera_id, s3_key
            """
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return {"id": str(row[0]), "camera_id": str(row[1]), "s3_key": row[2]}


def post_alert(api_base: str, token: str, payload: dict) -> dict:
    r = httpx.post(
        f"{api_base}/alerts/_internal",
        json=payload,
        headers={"X-Internal-Token": token},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def process_event(event: dict, *, conn, s3, bucket: str, api_base: str, token: str, yolo_filter: bool) -> None:
    rules = fetch_rules(conn, event["camera_id"])
    if not rules:
        log(f"  no enabled rules for cam={event['camera_id']}")
        return

    try:
        clip_path = _download_clip(s3, bucket, event["s3_key"])
    except Exception as e:  # noqa: BLE001
        log(f"  download failed key={event['s3_key']}: {e!r}")
        return

    try:
        for rule in rules:
            if not _is_active_now(rule.get("schedule")):
                log(f"  rule={rule['id']} outside schedule")
                continue
            yolo_conf = _yolo_confidence_from_sensitivity(rule.get("sensitivity"))
            intensity = rule.get("analysis_intensity") or "normal"
            label = rule.get("name") or "sem nome"
            log(f"  scoring rule={rule['id']} name={label!r} yolo_conf={yolo_conf} intensity={intensity}")
            try:
                result = score_clip(
                    str(clip_path),
                    rule.get("custom_prompt") or "",
                    rule.get("zones") or {},
                    yolo_filter=yolo_filter,
                    yolo_confidence=yolo_conf,
                    intensity=intensity,
                )
            except Exception as e:  # noqa: BLE001
                log(f"  vlm error: {e!r}")
                continue
            log(f"    alert={result.alert} score={result.score:.2f} msg={result.message[:160]}")
            if not result.alert:
                continue
            try:
                resp = post_alert(
                    api_base,
                    token,
                    {
                        "rule_id": str(rule["id"]),
                        "event_id": event["id"],
                        "score": result.score,
                        "message": result.message,
                    },
                )
                log(f"    alert posted id={resp.get('id')}")
            except httpx.HTTPError as e:
                log(f"    alert post failed: {e!r}")
    finally:
        try:
            clip_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    api_base = os.environ.get("CAMS_API", "http://localhost:8000")
    token = os.environ["CAMS_INTERNAL_TOKEN"]
    bucket = os.environ["CAMS_CLIPS_BUCKET"]
    db_url = _pg_dsn(os.environ["CAMS_DATABASE_URL"])
    poll_idle_s = float(os.environ.get("CAMS_POLL_IDLE_SECONDS", "5"))
    yolo_filter = _bool_env("CAMS_YOLO_FILTER", default=True)

    log(f"db worker starting; api={api_base} bucket={bucket} yolo_filter={yolo_filter}")
    s3 = _make_s3_client()

    while True:
        try:
            with psycopg.connect(db_url, autocommit=False) as conn:
                while True:
                    event = claim_event(conn)
                    if not event:
                        time.sleep(poll_idle_s)
                        continue
                    log(f"event {event['id']} cam={event['camera_id']} key={event['s3_key']}")
                    process_event(
                        event,
                        conn=conn,
                        s3=s3,
                        bucket=bucket,
                        api_base=api_base,
                        token=token,
                        yolo_filter=yolo_filter,
                    )
        except Exception as e:  # noqa: BLE001
            log(f"loop error, reconnecting in 5s: {e!r}")
            time.sleep(5)


if __name__ == "__main__":
    main()
