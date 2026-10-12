@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
python -m voxpilot.app.cli doctor %*
endlocal
