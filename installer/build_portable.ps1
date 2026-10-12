# VoxPilot Portable Bundle Builder
# Assembles a standalone portable distribution of VoxPilot under dist/voxpilot-portable/

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$distDir = Join-Path $repoRoot "dist\voxpilot-portable"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         VoxPilot Portable Distribution Packager          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Test-Path $distDir) {
    Write-Host "[*] Cleaning existing portable directory..." -ForegroundColor Yellow
    Remove-Item -Path $distDir -Recurse -Force
}

New-Item -ItemType Directory -Path $distDir -Force | Out-Null
Write-Host "[+] Created distribution root: $distDir" -ForegroundColor Green

# 1. Copy src
Write-Host "[*] Packaging source code..." -ForegroundColor Yellow
Copy-Item -Path (Join-Path $repoRoot "src") -Destination (Join-Path $distDir "src") -Recurse

# 2. Copy models
Write-Host "[*] Packaging offline Vosk speech models..." -ForegroundColor Yellow
Copy-Item -Path (Join-Path $repoRoot "models") -Destination (Join-Path $distDir "models") -Recurse

# 3. Copy Chromium extension
Write-Host "[*] Packaging Chromium MV3 extension..." -ForegroundColor Yellow
Copy-Item -Path (Join-Path $repoRoot "extensions") -Destination (Join-Path $distDir "extensions") -Recurse

# 4. Copy installer scripts
Write-Host "[*] Packaging installer utilities..." -ForegroundColor Yellow
Copy-Item -Path (Join-Path $repoRoot "installer") -Destination (Join-Path $distDir "installer") -Recurse

# 5. Create launcher batch files
Write-Host "[*] Creating launcher executables..." -ForegroundColor Yellow
$launcherContent = @"
@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
python -m voxpilot.app.tray %*
endlocal
"@
Set-Content -Path (Join-Path $distDir "voxpilot.bat") -Value $launcherContent -Encoding ASCII

$doctorContent = @"
@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
python -m voxpilot.app.cli doctor %*
endlocal
"@
Set-Content -Path (Join-Path $distDir "voxpilot-doctor.bat") -Value $doctorContent -Encoding ASCII

$cliContent = @"
@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
python -m voxpilot.app.cli %*
endlocal
"@
Set-Content -Path (Join-Path $distDir "voxpilot-cli.bat") -Value $cliContent -Encoding ASCII

# 6. Create Readme
$readmeContent = @"
==================================================================
                 VoxPilot Portable Edition
   Offline-First Voice Control & Dictation System for Windows
==================================================================

QUICK START:
1. Run 'voxpilot-doctor.bat' to verify your microphone and environment.
2. Run 'voxpilot.bat' to start the VoxPilot system tray application.
3. Use 'voxpilot-cli.bat say "show numbers"' to test commands via CLI.

BROWSER EXTENSION:
- Open chrome://extensions or edge://extensions
- Enable 'Developer Mode'
- Click 'Load Unpacked' and select the 'extensions/chromium' folder.
- Run 'powershell -ExecutionPolicy Bypass -File installer/install_native_host.ps1'

PRIVACY GUARANTEE:
- 100% Offline by default. Zero telemetry. Audio never leaves this PC.
==================================================================
"@
Set-Content -Path (Join-Path $distDir "README.txt") -Value $readmeContent -Encoding UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   PORTABLE BUNDLE BUILT SUCCESSFULLY AT:                 " -ForegroundColor Green
Write-Host "   $distDir" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
