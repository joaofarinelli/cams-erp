@echo off
REM cams-erp PDV agent launcher (Windows tray app).
REM Edit values below once, double-click to start.
setlocal

set CAMS_API=https://cams-erp-api.fly.dev
set CAMS_DEVICE_TOKEN=PUT_DEVICE_TOKEN_HERE
REM Leave RTSP_URL and CAMERA_ID empty for control-only mode (USB cams via web wizard).
set CAMS_RTSP_URL=
set CAMS_CAMERA_ID=

REM Bundled ffmpeg
set PATH=%~dp0ffmpeg;%PATH%

REM Launch without console window; tray app handles UI + autostart.
start "" "%~dp0cams-agent\cams-agent.exe"
