@echo off
echo ================================================
echo   Aurum Flow -- TikTok LIVE Overlay Server
echo ================================================
echo.
echo Starting overlay server...
echo.
echo Once started, add this URL in OBS:
echo   Browser Source ^> http://localhost:8765/overlay
echo.
echo Press Ctrl+C to stop.
echo.
cd /d "%~dp0.."
python live/overlay_server.py
pause
