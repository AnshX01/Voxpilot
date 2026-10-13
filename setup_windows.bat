@echo off
setlocal
cd /d "%~dp0"
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install --quiet -r requirements.txt
if not exist models\vosk-model-small-en-us-0.15 (
  powershell -NoProfile -Command "Invoke-WebRequest https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -OutFile m.zip; Expand-Archive m.zip models -Force; Remove-Item m.zip"
)
echo Setup done. Start with: run_voxpilot.bat
endlocal
