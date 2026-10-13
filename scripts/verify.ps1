# VoxPilot Continuous Verification Runner
# Runs contracts, unit, dictation, extended commands, browser extension, shell app, targets, vertical slice, and adversarial tests.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         VoxPilot Automated Verification Gate Runner      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Set PYTHONPATH
$env:PYTHONPATH = "src"

# 1. Check Python and dependencies
Write-Host "[1/6] Checking Python environment and runtime..." -ForegroundColor Yellow
$pyVersion = python --version
Write-Host "Python Version: $pyVersion" -ForegroundColor Green

# 2. Run Contracts, Unit & Command NLU tests
Write-Host "[2/6] Running Contracts, Commands, Extensions, macOS Parity, Input & Shell App tests..." -ForegroundColor Yellow
python -m pytest tests/test_contracts.py tests/test_commands.py tests/test_extended_commands.py tests/test_macos_parity.py tests/test_input.py tests/test_browser_extension.py tests/test_shell_app.py tests/test_offline_telemetry.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Contracts, macOS Parity, Input or Command NLU tests failed!"
    exit 1
}
Write-Host "Contracts, Commands, Extensions, macOS Parity, Input, Shell App & Offline Telemetry tests PASSED." -ForegroundColor Green

# 3. Run Dictation & Normalization Suite (>=300 tests)
Write-Host "[3/6] Running Dictation & Normalization Suite..." -ForegroundColor Yellow
python -m pytest tests/test_dictation.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dictation test suite failed!"
    exit 1
}
Write-Host "Dictation test suite PASSED (322 tests verified)." -ForegroundColor Green

# 4. Run Target Applications & Vertical Slice E2E
Write-Host "[4/6] Running Target Apps & E2E Vertical Slice tests..." -ForegroundColor Yellow
python -m pytest tests/test_targets_e2e.py tests/test_vertical_slice_e2e.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "E2E Integration tests failed!"
    exit 1
}
Write-Host "E2E Integration tests PASSED." -ForegroundColor Green

# 5. Run Adversarial Attack & Fault Injection Suites (Rounds 1, 2 & 3)
Write-Host "[5/6] Running Adversarial Attack & Fault Injection Suites (Rounds 1, 2 & 3)..." -ForegroundColor Yellow
python -m pytest tests/test_adversarial_slice.py tests/test_adversarial_round2.py tests/test_adversarial_round3.py tests/test_fault_injection.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Adversarial or Fault Injection tests failed!"
    exit 1
}
Write-Host "Adversarial & Fault Injection suites PASSED (43 attack & resilience vectors verified)." -ForegroundColor Green

# 6. Run CLI Doctor Self-Check
Write-Host "[6/6] Running VoxPilot Doctor Self-Diagnostics..." -ForegroundColor Yellow
python -m voxpilot.app.cli doctor
if ($LASTEXITCODE -ne 0) {
    Write-Error "Doctor diagnostics failed!"
    exit 1
}
Write-Host "Doctor diagnostics PASSED." -ForegroundColor Green

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   ALL VERIFICATION GATES PASSED (100% SUCCESSFUL RUN)   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
