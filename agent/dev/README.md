# cams-erp dev agent stub

Python stub of the production Go agent. Reads RTSP, motion-triggers clip recording, posts to Cloud API.

**Not production.** Real agent will be Go + gocv. This destrava end-to-end smoke testing during Phase 1, against a real IP camera (e.g. Intelbras iM5 SC).

## Setup

```bash
cd agent/dev
uv sync
```

## End-to-end local run

### 1. API with auth bypass + dev S3/SQS stubs

`CAMS_AUTH_BYPASS=1` does three things:
- `get_current_user` returns a synthetic dev user (no Cognito needed)
- `signed_put_url()` returns `http://localhost:8000/dev/s3/<key>` (file-backed at `/tmp/cams-erp-clips/`)
- `enqueue_event()` appends to `/tmp/cams-erp-events.log` (no SQS)

```bash
cd api
PYTHONPATH=. \
  CAMS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/postgres \
  CAMS_AUTH_BYPASS=1 \
  uv run uvicorn app.main:app --reload
```

Postgres assumed at `localhost:5432` (run `docker run -d --name camserp-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16` once). Apply migrations: `PYTHONPATH=. CAMS_DATABASE_URL=... uv run alembic upgrade head`.

### 2. Pair a device + register the camera

```bash
PAIR=$(curl -s -X POST http://localhost:8000/pair/code | jq -r .pair_code)
DEVICE_ID=$(curl -s -X POST http://localhost:8000/pair/code | jq -r .device_id)
DEV_TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"pair_code\":\"$PAIR\"}" http://localhost:8000/pair/verify | jq -r .device_token)
CAM_ID=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"name\":\"Cam 1\",\"rtsp_url\":\"rtsp://USER:SENHA@CAM_IP:554/cam/realmonitor?channel=1&subtype=1\",\"device_id\":\"$DEVICE_ID\"}" \
  http://localhost:8000/cameras | jq -r .id)
echo "DEV_TOKEN=$DEV_TOKEN  CAM_ID=$CAM_ID"
```

### 3. Run the agent

```bash
cd agent/dev
uv run python agent.py \
  --rtsp "rtsp://USER:SENHA@CAM_IP:554/cam/realmonitor?channel=1&subtype=1" \
  --device-token "$DEV_TOKEN" \
  --camera-id "$CAM_ID"
```

Wave at the camera. Expected log:

```
connecting RTSP: rtsp://...
stream: 640x480 @ 15.0fps
motion 0.018 -> recording 5s
heartbeat -> 200
upload-url ok: s3_key=clips/.../xxx.mp4
clip uploaded
event ack: id=... enqueued=True
```

### 4. Inspect the artefacts

```bash
ls -la /tmp/cams-erp-clips/clips/      # the saved clips
cat /tmp/cams-erp-events.log           # one JSON per event
curl http://localhost:8000/alerts       # empty until inference worker exists
```

## Windows .exe (PDV)

Build via GitHub Actions: push to `main` ou `workflow_dispatch` em `Build PDV agent (Windows .exe)`. Artifact `cams-agent-windows.zip` aparece na run.

Conteúdo do zip:
- `cams-agent/cams-agent.exe` + libs
- `ffmpeg/ffmpeg.exe` + `ffprobe.exe`
- `run-agent.bat` (editar token/RTSP/camera_id, dar duplo-clique)
- `README.md`

Local build (Windows host):

```powershell
cd agent\dev
pip install -r <(echo opencv-python==4.10.0.84 httpx==0.27.2 numpy==1.26.4 websockets==12.0 pyinstaller==6.10.0)
pyinstaller agent.spec --noconfirm
```

Saída em `dist/cams-agent/`. Copiar `ffmpeg.exe` ao lado ou colocar no PATH.

Auto-start no boot (Windows): adicionar atalho de `run-agent.bat` em `shell:startup`.

## Tunables

- `--motion-threshold 0.02` (0..1, mean of binarized 320x240 frame diff). Raise if false-trigger; lower if motion missed. Confirmed working values for the iM5 SC sub-stream: 0.005-0.02.
- `--cooldown 15` seconds between triggers
- `--clip-seconds 5` length of recorded clip
- `--heartbeat 30` seconds between heartbeats
