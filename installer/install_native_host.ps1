# VoxPilot Chromium/Edge Native Messaging Host Registration Script
# Registers com.voxpilot.host in the Current User registry for Google Chrome and Microsoft Edge.

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$manifestSource = Join-Path $repoRoot "src\voxpilot\native_host\com.voxpilot.host.json"
$targetManifestDir = Join-Path $env:LOCALAPPDATA "VoxPilot\NativeHost"
$targetManifestPath = Join-Path $targetManifestDir "com.voxpilot.host.json"
$hostScript = Join-Path $repoRoot "src\voxpilot\native_host\host.py"
$pythonExe = (Get-Command python.exe).Source

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   VoxPilot Native Messaging Host Windows Installer       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path $targetManifestDir)) {
    New-Item -ItemType Directory -Path $targetManifestDir -Force | Out-Null
}

# Generate launcher batch file for Chrome/Edge
$launcherBatchPath = Join-Path $targetManifestDir "voxpilot_native_host.bat"
$batchContent = "@echo off`r`n`"$pythonExe`" `"$hostScript`" %*`r`n"
Set-Content -Path $launcherBatchPath -Value $batchContent -Encoding ASCII

# Generate JSON manifest pointing to the launcher batch
$manifestObj = @{
    name = "com.voxpilot.host"
    description = "VoxPilot Native Messaging Host for Chromium/Edge"
    path = $launcherBatchPath
    type = "stdio"
    allowed_origins = @(
        "chrome-extension://voxpilot-dev-extension/"
    )
}

$manifestJson = $manifestObj | ConvertTo-Json -Depth 4
Set-Content -Path $targetManifestPath -Value $manifestJson -Encoding UTF8
Write-Host "[+] Generated Native Messaging manifest at: $targetManifestPath" -ForegroundColor Green

# Register in HKCU for Google Chrome
$chromeRegPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.voxpilot.host"
if (-not (Test-Path $chromeRegPath)) {
    New-Item -Path $chromeRegPath -Force | Out-Null
}
Set-ItemProperty -Path $chromeRegPath -Name "(Default)" -Value $targetManifestPath
Write-Host "[+] Registered in Chrome Registry: $chromeRegPath" -ForegroundColor Green

# Register in HKCU for Microsoft Edge
$edgeRegPath = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.voxpilot.host"
if (-not (Test-Path $edgeRegPath)) {
    New-Item -Path $edgeRegPath -Force | Out-Null
}
Set-ItemProperty -Path $edgeRegPath -Name "(Default)" -Value $targetManifestPath
Write-Host "[+] Registered in Edge Registry: $edgeRegPath" -ForegroundColor Green

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   NATIVE MESSAGING HOST SUCCESSFULLY INSTALLED & LINKED  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
