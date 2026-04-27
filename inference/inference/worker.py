"""Inference worker.

Loop:
  1. Tail /tmp/cams-erp-events.log (dev stub) — JSONL, one event per line.
  2. For each event, fetch the rules of the camera via the API.
  3. For each enabled rule, sample frames from the saved clip and score with
     Claude Haiku 4.5 vision.
  4. If alert==True, POST /alerts/_internal — the API persists the Alert and
     publishes via the in-process broker so mobile WS receives push.

Production swaps step 1 for an SQS consumer and step 4 for a direct DB
write + same broker call (or Redis pub/sub).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

from inference.vlm import score_clip


def _bool_env(name: str, default: bool = True) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _yolo_confidence_from_sensitivity(sensitivity: int | None) -> float:
    """sensitivity 0..100 -> yolo conf 0.7..0.1 (higher sensitivity = looser)."""
    if sensitivity is None:
        return 0.35
    s = max(0, min(100, int(sensitivity)))
    return round(0.7 - (s / 100.0) * 0.6, 3)


def _is_active_now(schedule: dict | None) -> bool:
    """Mirror app/services/schedule.py for worker-side filtering."""
    if not schedule:
        return True
    from datetime import datetime
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
        if start <= end:
            if start <= cur <= end:
                return True
        else:
            if cur >= start or cur <= end:
                return True
    return False


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_rules_for_camera(api_base: str, camera_id: str) -> list[dict]:
    r = httpx.get(f"{api_base}/rules", timeout=10)
    r.raise_for_status()
    return [rule for rule in r.json() if rule["camera_id"] == camera_id and rule["enabled"]]


def post_alert(api_base: str, payload: dict) -> dict:
    r = httpx.post(f"{api_base}/alerts/_internal", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def tail_events(log_path: Path, state_path: Path):
    """Yield JSON event dicts as lines are appended. Persists offset so the
    worker can be restarted without reprocessing."""
    pos = 0
    if state_path.exists():
        try:
            pos = int(state_path.read_text().strip() or "0")
        except ValueError:
            pos = 0
    log(f"tailing {log_path} from offset {pos}")
    while True:
        if log_path.exists():
            with log_path.open() as f:
                f.seek(pos)
                line = f.readline()
                while line:
                    s = line.strip()
                    if s:
                        try:
                            yield json.loads(s)
                        except json.JSONDecodeError:
                            log(f"skipping malformed line: {s[:80]!r}")
                    pos = f.tell()
                    state_path.write_text(str(pos))
                    line = f.readline()
        time.sleep(2)


def process_event(event: dict, *, api_base: str, clips_dir: Path, yolo_filter: bool = True) -> None:
    camera_id = event.get("camera_id")
    s3_key = event.get("s3_key")
    event_id = event.get("event_id")
    if not (camera_id and s3_key and event_id):
        log(f"skip event missing fields: {event}")
        return

    clip_path = clips_dir / s3_key
    if not clip_path.exists():
        log(f"clip missing on disk: {clip_path}")
        return

    try:
        rules = fetch_rules_for_camera(api_base, camera_id)
    except httpx.HTTPError as e:
        log(f"rules fetch failed: {e!r}")
        return

    if not rules:
        log(f"  no enabled rules for camera {camera_id}")
        return

    for rule in rules:
        if not _is_active_now(rule.get("schedule")):
            log(f"  rule={rule['id']} outside schedule, skipping")
            continue
        preset = rule["preset_type"]
        zones = rule.get("zones", {}) or {}
        custom_prompt = rule.get("custom_prompt")
        sensitivity = rule.get("sensitivity")
        yolo_conf = _yolo_confidence_from_sensitivity(sensitivity)
        label = "custom" if custom_prompt else preset
        log(f"  scoring rule={rule['id']} type={label} yolo_conf={yolo_conf} sens={sensitivity}")
        try:
            result = score_clip(
                str(clip_path), preset, zones,
                custom_prompt=custom_prompt,
                yolo_filter=yolo_filter,
                yolo_confidence=yolo_conf,
            )
        except Exception as e:  # noqa: BLE001
            log(f"  vlm error: {e!r}")
            continue
        log(f"    alert={result.alert} score={result.score:.2f} msg={result.message[:80]}")
        if not result.alert:
            continue
        try:
            resp = post_alert(
                api_base,
                {
                    "rule_id": rule["id"],
                    "event_id": event_id,
                    "score": result.score,
                    "message": result.message,
                },
            )
            log(f"    alert created id={resp.get('id')}")
        except httpx.HTTPError as e:
            log(f"  alert post failed: {e!r}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("CAMS_API", "http://localhost:8000"))
    p.add_argument("--events-log", default="/tmp/cams-erp-events.log")
    p.add_argument("--state-file", default="/tmp/cams-erp-inference-state")
    p.add_argument("--clips-dir", default="/tmp/cams-erp-clips")
    p.add_argument(
        "--no-yolo",
        action="store_true",
        help="Disable the YOLOv8n person filter; send every clip to the VLM.",
    )
    args = p.parse_args()
    yolo_filter = (not args.no_yolo) and _bool_env("CAMS_YOLO_FILTER", default=True)

    log(f"inference worker starting; api={args.api} clips={args.clips_dir} yolo_filter={yolo_filter}")
    for event in tail_events(Path(args.events_log), Path(args.state_file)):
        log(f"event {event.get('event_id')} cam={event.get('camera_id')}")
        process_event(event, api_base=args.api, clips_dir=Path(args.clips_dir), yolo_filter=yolo_filter)


if __name__ == "__main__":
    main()
