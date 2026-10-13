@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
.venv\Scripts\python -m voxpilot.app.tray %*
endlocal
