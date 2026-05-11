@echo off
REM cams-erp PDV agent launcher (Windows tray app).
REM Edit values below once, double-click to start.
setlocal

set CAMS_API=https://cams-erp-api.fly.dev
set CAMS_DEVICE_TOKEN=PUT_DEVICE_TOKEN_HERE
REM Leave RTSP_URL and CAMERA_ID empty for control-only mode (USB cams via web wizard).
set CAMS_RTSP_URL=
set CAMS_CAMERA_ID=
REM Edge YOLO pre-filter: only uploads clips when a person is detected inside
REM the camera's rule zones. Cuts cloud cost 70-90%% on idle cameras. Set "true"
REM to enable; leave empty/unset to disable.
REM set CAMS_EDGE_YOLO=true
REM set CAMS_EDGE_YOLO_CONF=0.35

REM Bundled ffmpeg
set PATH=%~dp0ffmpeg;%PATH%

REM Launch without console window; tray app handles UI + autostart.
start "" "%~dp0cams-agent\cams-agent.exe"
