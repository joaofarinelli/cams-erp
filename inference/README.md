# cams-erp inference worker (VLM, Claude Haiku 4.5)

Zero-shot vision worker. Reads events appended to `/tmp/cams-erp-events.log`,
scores the saved clip with Claude Haiku 4.5 vision (4 frames per clip,
preset-specific prompt), and POSTs alerts back to the API.

**Phase 2.0 stub.** Production replaces:
- File-tail event source → SQS consumer
- HTTP POST `/alerts/_internal` → direct DB write + same broker call (or Redis pub/sub)
- Heuristic VLM-only path → hybrid (YOLOv8n filter → VLM only on positives) once volume justifies the optimization

## Setup

```bash
cd inference
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
```

The API must be running with `CAMS_AUTH_BYPASS=1` so the worker can reach
`POST /alerts/_internal` (the endpoint 404s when bypass is off).

## End-to-end local run

Terminal 1 — API + dev stubs (Postgres assumed at `localhost:5432`):

```bash
cd api
PYTHONPATH=. \
  CAMS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/postgres \
  CAMS_AUTH_BYPASS=1 \
  uv run uvicorn app.main:app --reload
```

Terminal 2 — pair, register a camera, attach a rule (see `agent/dev/README.md`).

Terminal 3 — agent stub against mediamtx loop or a real RTSP camera (see `agent/dev/README.md`). Each motion → a new line in `/tmp/cams-erp-events.log`.

Terminal 4 — inference worker:

```bash
cd inference
ANTHROPIC_API_KEY=sk-ant-... uv run python -m inference.worker
```

Expected log:

```
inference worker starting; api=http://localhost:8000 clips=/tmp/cams-erp-clips
tailing /tmp/cams-erp-events.log from offset 0
event <event_id> cam=<camera_id>
  scoring rule=<rule_id> preset=cash_register
    alert=True score=0.84 msg=Mao na gaveta sem operacao no PC (frame 2)
    alert created id=<alert_id>
```

Inspect alerts via the API:

```bash
curl http://localhost:8000/alerts | jq
```

Mobile / browser WS clients connected to `/alerts/stream` receive the new
alert in real time (the API publishes via the in-process broker).

## Tunables

- `--api`: API base URL (default `http://localhost:8000`)
- `--events-log`: path to the JSONL event source (default `/tmp/cams-erp-events.log`)
- `--state-file`: where to persist the read offset (default `/tmp/cams-erp-inference-state`)
- `--clips-dir`: where to find the clips referenced by `s3_key` (default `/tmp/cams-erp-clips`)

## Cost

`claude-haiku-4-5` vision pricing (2026-04): $1.00 / 1M input tokens,
$5.00 / 1M output tokens. A 4-frame clip at 640x480 costs roughly
$0.003-$0.01 per scored event depending on prompt cache hit rate.

System prompt is cached (`cache_control: ephemeral`) — the per-preset
header is reused across many events without paying full input price.

## Tests

```bash
uv run pytest -v
```

7 tests, ~12s. The VLM call itself is mocked — tests do not hit the network.
