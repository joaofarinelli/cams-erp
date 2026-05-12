# cams-erp — Privacy Data Flow

Documents who touches video pixels and when, for LGPD compliance (RIPD reference).

Last updated: 2026-05-12

## Overview

cams-erp uses motion-triggered clips — NOT continuous streaming. A clip (8-30s) is only created when motion is detected. The flow:

1. Agent captures motion frame → decides clip boundaries
2. Agent uploads clip to S3 (encrypted in transit via TLS)
3. Inference worker downloads clip to a temp file → extracts peak frames into memory → sends to VLM
4. VLM returns text verdict (no pixel retained by VLM)
5. Alert (text + metadata) stored in DB; clip stays in S3 for retention_days then purged

## Step-by-step Data Flow

### 1. Edge capture (agent/dev/, Windows PDV PC)

- **Input:** RTSP stream or HTTP snapshot from camera
- **Processing:** MOG2 background subtraction detects motion; YOLO pre-filter (optional)
- **Output:** short clip (mp4, 8-30s) in local ring buffer (retention: 24h max)
- **PII in scope:** employee faces, body movement, LPR plates (if enabled)
- **Persistence:** local ring buffer at `buffer_root()` (chmod 700), clip files chmod 600
- **Cleanup:** ring buffer auto-rotates; remote `purge_clips` command clears immediately

### 2. Upload to S3 (agent → AWS S3 sa-east-1)

- **Mechanism:** agent calls `POST /clips/upload-url` → gets presigned S3 PUT URL (10min TTL) → uploads directly
- **Encryption:** TLS 1.2+ in transit; S3 SSE-S3 at rest
- **Path:** `clips/{device_id}/{camera_id}/{date}/{uuid}.mp4`
- **Retention:** per `Camera.retention_days` (default 7d); cron purges daily at 03:00 BRT

### 3. Inference worker (inference/, Fly.io GPU)

- **Input:** polls `events` table (FOR UPDATE SKIP LOCKED) → downloads clip from S3 via `boto3.download_file`
- **Temp file:** clip written to `tempfile.mkstemp(suffix=".mp4")` — required by `cv2.VideoCapture`; chmod inherits process umask; path never exposed outside worker process
- **Frame extraction:** `cv2.VideoCapture(clip_path)` reads frames into numpy arrays in process memory; no secondary disk write
- **Motion-peak selection:** `sample_frames_motion_peak()` — computes inter-frame L1 delta on 160×90 grayscale thumbnails; selects top-N frames by motion score; all in-memory numpy arrays
- **YOLO zone filter (optional):** `person_in_any_zone()` runs on in-memory frame array; no disk write; if no person detected, VLM call is skipped entirely
- **Zone overlay:** `overlay_zones()` draws translucent polygons onto a copy of each frame numpy array; in-memory only
- **VLM encoding:** `encode_frame()` calls `cv2.imencode(".jpg", frame)` → `buf.tobytes()` → `base64.standard_b64encode()`; result is a base64 string in memory; **no file written**
- **VLM call pattern:**
  - Stage 1: frames sent as `data:image/jpeg;base64,...` inline in HTTPS POST to OpenRouter (or configured provider) via OpenAI-compatible client
  - Default model: `google/gemini-2.0-flash-lite-001` (configurable via `CAMS_VLM_MODEL`)
  - Cascade (optional): if stage 1 score is ambiguous (`cascade_min ≤ score ≤ cascade_max`) and `CAMS_VLM_CASCADE_MODEL` is set, a second call is made with a stronger model and +2 frames
  - Sub-processor retains data per their DPA (OpenRouter/Google/OpenAI); no training use per standard DPA terms
- **Output:** text verdict (`AlertResult.message`) + score → posted to Cloud API as Alert
- **Frame lifetime:** frames exist only in worker process memory during inference; numpy arrays are GC'd after `score_clip()` returns; no disk write beyond the temp clip file
- **Temp clip cleanup:** `finally: clip_path.unlink(missing_ok=True)` at `db_worker.py:240` — guaranteed cleanup after each event, even on exception
- **Clip in S3:** not deleted by inference worker; governed by retention_days schedule

### 4. Alert storage (Cloud API + PostgreSQL)

- **Stored:** `Alert.message` (text only), `Alert.score`, `Alert.created_at`, reference to event (`s3_key`)
- **NOT stored:** raw frames, frame embeddings (unless `face_recognition_enabled`), audio waveforms
- **Access:** owner via JWT-authenticated endpoints; audit log records every access

### 5. Purge paths

| Trigger | Target | Mechanism |
|---------|--------|-----------|
| `retention_days` elapsed | S3 clips | `clip_retention_scheduler` (daily 03:00 BRT) |
| `DELETE /me` | User data + S3 clips | soft-delete + `purge_clips` control command |
| Ring buffer rotation | Local clips | 24h TTL auto-rotation |
| Remote `purge_clips` | Agent ring buffer | Control WS → `shutil.rmtree` + recreate |

### 6. Sub-processor frame exposure

Frames (video stills) are sent to:

- **OpenRouter** (default gateway) — routes to the configured vision model (default `google/gemini-2.0-flash-lite-001`). Sent as HTTPS POST with base64-encoded JPEG inline in request body. Sub-processor processes and returns text; no storage beyond processing buffer. Governed by OpenRouter ToS / Google DPA.
- **OpenAI / Anthropic / other VLM providers** (opt-in via `CAMS_VLM_BASE_URL` + `CAMS_VLM_MODEL`) — same mechanism. Governed by respective provider DPA.
- **OpenALPR Cloud** (opt-in only, `lpr_enabled`) — JPEG frame crop sent for plate reading. Governed by OpenALPR DPA.

Frames are NOT sent to: Sentry, Stripe, Evolution API, Expo Push, Fly.io (Fly hosts the worker process but frames never leave process memory to Fly's storage layer), YOLO (runs locally inside the worker).

## Legal Basis

- Surveillance: **Legítimo interesse** (art. 7º IX LGPD) — security and loss prevention
- Face recognition / audio: **Consentimento** (art. 7º I) — explicit opt-in per camera
- Billing data: **Execução de contrato** (art. 7º V)

## Retention Summary

| Data type | Retention | Deletion mechanism |
|-----------|-----------|-------------------|
| Video clips (S3) | 7d default (configurable 1-90d) | `clip_retention_scheduler` |
| Agent ring buffer | 24h | Auto-rotation + `purge_clips` |
| Inference temp clip | Single event duration (~seconds) | `clip_path.unlink()` in `finally` block |
| Alert metadata | 90d (`CAMS_RETENTION_DAYS_ALERTS`) | TBD cron |
| Audit log | 12 months | `audit.purge_old_entries()` |
| User account | 30d grace after `DELETE /me` | `account_purge_scheduler` |
| Consent log | Indefinite (legal compliance) | Not purged |
| Billing records | Stripe-managed | Stripe DPA |
