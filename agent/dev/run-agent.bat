@echo off
REM cams-erp PDV agent launcher (Windows).
REM Edit the values below once, double-click to start.

set API=https://cams-erp-api.fly.dev
set DEVICE_TOKEN=PUT_DEVICE_TOKEN_HERE
set RTSP=
set CAMERA_ID=
set HEARTBEAT=30

REM Add bundled ffmpeg to PATH
set PATH=%~dp0ffmpeg;%PATH%

"%~dp0cams-agent\cams-agent.exe" ^
  --api %API% ^
  --device-token %DEVICE_TOKEN% ^
  --rtsp "%RTSP%" ^
  --camera-id %CAMERA_ID% ^
  --heartbeat %HEARTBEAT%

pause
