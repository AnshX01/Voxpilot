# One-shot Windows check for the Voice Control parity branch (UNTESTED on Windows by the author).
# Usage (PowerShell, from repo root):  powershell -ExecutionPolicy Bypass -File scripts\windows_verify_parity.ps1
$ErrorActionPreference = "Stop"
python -m venv .venv
.\.venv\Scripts\python -m pip install --quiet pytest numpy PySide6 psutil vosk uiautomation comtypes sounddevice faster-whisper
if (-not (Test-Path models\vosk-model-small-en-us-0.15)) {
  Invoke-WebRequest https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -OutFile m.zip
  Expand-Archive m.zip models; Remove-Item m.zip
}
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m pytest -q tests 2>&1 | Tee-Object -FilePath verify_log.txt
Write-Host "`nTest log saved to verify_log.txt. Launching VoxPilot: try 'show numbers', 'show grid', 'show text numbers', 'show commands'."
.\.venv\Scripts\python -m voxpilot.app.tray
