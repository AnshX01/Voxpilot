@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found on PATH. Install Python 3.11 from python.org and tick "Add python.exe to PATH", then run this again.
  exit /b 1
)
if not exist .venv (
  python -m venv .venv
  if errorlevel 1 ( echo ERROR: could not create virtual environment. & exit /b 1 )
)
.venv\Scripts\python -m pip install --quiet -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed. See the messages above. & exit /b 1 )
if not exist models\vosk-model-small-en-us-0.15 (
  powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -OutFile m.zip; Expand-Archive m.zip models -Force; Remove-Item m.zip"
  if errorlevel 1 ( echo ERROR: Vosk model download failed. & exit /b 1 )
)
if not exist models\vosk-model-small-en-us-0.15 (
  echo ERROR: Vosk model folder missing after download.
  exit /b 1
)
echo Setup done. Start with: run_voxpilot.bat
endlocal
