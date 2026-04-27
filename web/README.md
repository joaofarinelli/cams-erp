# cams-erp web dashboard

Dev-only operator dashboard. Vite + React + TS, ~150 LOC.

Three tabs:
- **Alertas** — live feed via WS `/alerts/stream`, plays the captured clip inline, confirm / mark false-positive
- **Câmeras** — list with online status + rules per camera
- **Regras** — create new rule (preset + optional name + optional pt-BR custom prompt)

Talks to the API via the Vite dev proxy at `/api` so you don't need CORS.
The API must be running at `localhost:8000` with `CAMS_AUTH_BYPASS=1`.

## Setup

```bash
cd web
npm install
npm run dev
```

Open <http://localhost:5173>.

## Build

```bash
npm run build
npm run preview
```

`dist/` is statically deployable behind any HTTP server. In production swap
the `/api` proxy for the real API hostname and replace bypass auth with
Cognito.
