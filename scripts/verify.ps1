# VoxPilot Continuous Verification Runner
# Runs build, contracts, commands, targets, vertical slice, and adversarial tests.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         VoxPilot Automated Verification Gate Runner      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python and dependencies
Write-Host "[1/4] Checking Python environment and runtime..." -ForegroundColor Yellow
$pyVersion = python --version
Write-Host "Python Version: $pyVersion" -ForegroundColor Green

# 2. Run Contracts & Unit Tests
Write-Host "[2/4] Running Contracts and Command NLU tests..." -ForegroundColor Yellow
python -m pytest tests/test_contracts.py tests/test_commands.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Contracts or Command NLU tests failed!"
    exit 1
}
Write-Host "Contracts and Command NLU tests PASSED." -ForegroundColor Green

# 3. Run Target Applications & Vertical Slice E2E
Write-Host "[3/4] Running Target Apps & E2E Vertical Slice tests..." -ForegroundColor Yellow
python -m pytest tests/test_targets_e2e.py tests/test_vertical_slice_e2e.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "E2E Integration tests failed!"
    exit 1
}
Write-Host "E2E Integration tests PASSED." -ForegroundColor Green

# 4. Run Adversarial Attack Suite
Write-Host "[4/4] Running Adversarial Attack Suite..." -ForegroundColor Yellow
python -m pytest tests/test_adversarial_slice.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Adversarial tests failed!"
    exit 1
}
Write-Host "Adversarial suite PASSED." -ForegroundColor Green

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   ALL VERIFICATION GATES PASSED (100% SUCCESSFUL RUN)   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
