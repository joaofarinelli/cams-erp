# cams-erp

[![Build PDV agent (Windows)](https://github.com/joaofarinelli/cams-erp/actions/workflows/build-agent-windows.yml/badge.svg)](https://github.com/joaofarinelli/cams-erp/actions/workflows/build-agent-windows.yml)
![tests](https://img.shields.io/badge/tests-82_passing-brightgreen)
![python](https://img.shields.io/badge/python-3.12-blue)

**Vigilância inteligente em português pra varejo PME brasileiro.**

Cliente descreve regra em linguagem natural ("avise se a gaveta do
caixa for aberta", "alerte se alguém comer escondido na cozinha"). Um
agente leve roda no PDV do cliente, filtra movimento na borda
(MOG2 + YOLO local), envia o clip relevante pra cloud, e um VLM (Gemini
Flash Lite / Claude Sonnet em cascade) decide se o evento descrito
ocorreu. Alerta vai pro WhatsApp + push mobile + toast no PDV.

## Por que isso existe

Câmera de segurança comum só grava. Cliente PME precisa que **alguém
olhe** as gravações, e ninguém olha. cams-erp transforma "ter câmera" em
"ser avisado quando algo importa", **sem trocar câmera**, **sem alarme
falso de vento e sombra**, em **português**.

## Stack

```
DVR/IP cam (LAN)
       │ RTSP/HTTP snapshot
       ▼
┌────────────────────────────────┐
│ Windows Agent (PyInstaller)    │   • motion detection (MOG2)
│ - CameraWorkerPool             │   • edge YOLOv8n (ONNX)
│ - Edge YOLO + dedup            │   • per-cam 24h ring buffer
│ - 24h JPEG ring buffer         │   • Tkinter pairing GUI
│ - Pairing GUI + tray app       │   • auto-update via GH Releases
│ - Crash reporter + self-test   │   • crash reports + self-test
└──────────────┬─────────────────┘
               │ control WS + HTTP
               ▼
┌────────────────────────────────┐
│ Cloud API (Fly.io)             │   • FastAPI + Postgres (Supabase)
│ - /events, /clips, /alerts     │   • S3/R2 clips
│ - /agent/control WS            │   • SQS event queue
│ - /webhooks/stripe             │   • Stripe billing
│ - /usage/me + quotas           │
└──────────────┬─────────────────┘
               │ SQS
               ▼
┌────────────────────────────────┐
│ Inference worker (Fly.io)      │   • YOLO zone filter
│ - Motion-peak frame selection  │   • VLM cascade (Flash Lite → Pro)
│ - Cloud YOLO zone filter       │   • per-rule intensity profiles
│ - Cascade VLM                  │
└──────────────┬─────────────────┘
               │ /alerts/_internal
               ▼
┌────────────────────────────────┐
│ Alert fan-out                  │
│ - WhatsApp (Evolution API)     │
│ - Push (Expo)                  │
│ - Toast no agent (win11toast)  │
│ - Web app (cams-erp-web)       │
└────────────────────────────────┘
```

## Workspaces

- `agent/dev/` — Windows tray agent (Python + PyInstaller). Edge YOLO,
  MOG2 motion, 24h ring buffer, pairing GUI, auto-update.
- `api/` — Cloud API (FastAPI + asyncpg). Pairing, events, alerts,
  clips, usage/billing, Stripe webhooks.
- `inference/` — GPU/CPU worker (Python). YOLO + VLM cascade pipeline.
- `web/` — Painel (React + Vite + Tailwind), deploy via Cloudflare Pages.
- `mobile/` — Owner app (React Native + Expo).

## Quick start

**Cliente final:**
1. Cria conta em https://cams-erp-web.pages.dev
2. Gera pair code → instala agent (`run-agent.bat`) → cola código
3. Cadastra câmeras pelo wizard (ONVIF bulk ou DVR Hikvision ISAPI)
4. Escreve regras em português → recebe alertas no WhatsApp

Detalhes em [DEPLOY.md](./DEPLOY.md).

**Desenvolvedor:**
```bash
# Backend
docker compose -f docker-compose.dev.yml up -d postgres
cd api && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app

# Web
cd web && npm install && npm run dev

# Inference worker
cd inference && uv sync && uv run python -m inference.db_worker

# Agent (Mac dev sem builder)
cd agent/dev && uv sync && uv run python tray.py
```

## Tests

```
cd api && uv run pytest tests/         # 52 tests
cd inference && uv run pytest tests/   # 12 tests
cd agent/dev && .venv/bin/python -m pytest tests/  # 18 tests
```

Total: **82 testes passando**.

## Pricing

| Plano | Base/mês | Câmeras | Câmera extra |
|-------|----------|---------|--------------|
| Starter | R$ 197 | 2 | R$ 47 |
| Pro | R$ 497 | 5 | R$ 87 |
| Business | R$ 1.497 | 20 | R$ 67 |
| Enterprise | sob consulta | — | — |

Trial 14 dias grátis. Sem fidelidade. Pix/boleto/cartão via Stripe BR.

## Links

- Painel web: https://cams-erp-web.pages.dev
- API: https://cams-erp-api.fly.dev
- Operação: [DEPLOY.md](./DEPLOY.md)
- Roadmap: ver `superpowers/plans/`
