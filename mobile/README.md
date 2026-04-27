# cams-erp mobile

React Native (Expo Router + TypeScript). Owner-facing app: alert feed, clip
playback, feedback (confirm / mark false positive).

## Screens

- `/` — alert list, refreshable, WebSocket subscription to `/alerts/stream`
  for real-time push (status dot in the header)
- `/alert/[id]` — single alert detail with inline video player
  (`expo-av`), confirm / false-positive buttons that hit
  `/alerts/{id}/feedback`

## Setup

```bash
cd mobile
npm install
npx expo start
```

Press `i` (iOS sim), `a` (Android emulator), or `w` (web). Scan the QR
code with the Expo Go app on a physical device.

The API base URL lives in `app.json` → `expo.extra.apiBase`. Default is
`http://localhost:8000`. Override per-build for staging/prod, or for a
device on the same Wi-Fi (use the laptop's LAN IP, not `localhost`):

```bash
APP_API_BASE=http://192.168.0.150:8000 npx expo start
```

(The current build reads `app.json` at compile time; for dynamic config
move it to `app.config.js`. Phase 3 cleanup.)

## What's not here yet

- **Auth** — bypassed via `CAMS_AUTH_BYPASS=1` on the API. Cognito wiring is
  Phase 3.
- **Push notifications** — the in-app WS handles foreground push; APNs/FCM
  via `expo-notifications` is Phase 3.
- **Live RTSP view** — out of MVP per `deferred_decisions.md`. Owner uses
  the camera vendor app for live; differential is the AI alert feed.

## Build

```bash
# Standalone iOS / Android
npx expo prebuild
npx expo run:ios
npx expo run:android

# Web (debug only — the production web app is in /web)
npx expo export -p web
```
