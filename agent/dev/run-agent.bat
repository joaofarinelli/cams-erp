@echo off
REM cams-erp PDV agent launcher.
REM
REM First run: a janela GUI vai pedir o código de pareamento gerado no painel
REM web. Depois disso, não precisa editar mais nada — o agent salva o token
REM em %LOCALAPPDATA%\cams-agent\config.json e busca a lista de câmeras /
REM zonas / regras direto do servidor. Tudo é controlado pelo painel web.
REM
REM (Para mudar API URL ou forçar dev/staging, exporte CAMS_API antes do
REM start abaixo. Não é necessário em produção.)
setlocal

REM ffmpeg bundled with the release zip.
set PATH=%~dp0ffmpeg;%PATH%

start "" "%~dp0cams-agent\cams-agent.exe"
