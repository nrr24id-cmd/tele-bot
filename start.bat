@echo off
cd /d "%~dp0"

start /b "" .venv\Scripts\pythonw -m sn_forwarder.main > sn_panel.log 2>&1

timeout /t 3 /nobreak >nul

start /b "" .venv\Scripts\python start_tunnel.py > tunnel.log 2>&1
