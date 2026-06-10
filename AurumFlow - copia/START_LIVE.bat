@echo off
title Aurum Flow — LIVE Mode
color 0A

echo.
echo  ================================================
echo    AURUM FLOW — TIKTOK LIVE LAUNCHER
echo  ================================================
echo.
echo  Arrancando sistema completo...
echo.

cd /d "%~dp0"

echo  [1/2] Iniciando overlay server (puerto 8765)...
start "Aurum Flow Overlay" cmd /k "python live/overlay_server.py"

timeout /t 3 /nobreak >nul

echo  [2/2] Iniciando bot de señales...
echo.
echo  ================================================
echo    TODO LISTO. Ahora:
echo.
echo    1. Abre OBS
echo    2. Añade Browser Source:
echo       URL: http://localhost:8765/overlay
echo       W: 1080  H: 1920
echo    3. Pon OBS en modo LIVE (1080x1920 / 30fps)
echo    4. Empieza el LIVE en TikTok
echo  ================================================
echo.

python main.py
