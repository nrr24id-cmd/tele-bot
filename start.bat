@echo off
echo Starting SN Forwarder Platform...

start "SN Panel" cmd /k "cd /d "%~dp0" && set PYTHONPATH=src && .venv\Scripts\python -m sn_forwarder.main"

timeout /t 3 /nobreak >nul

start "Cloudflare Tunnel" cmd /k "cd /d "%~dp0" && .venv\Scripts\python start_tunnel.py"

echo.
echo Dua terminal sudah dibuka.
echo URL tunnel akan dikirim otomatis ke Telegram kamu.
pause
