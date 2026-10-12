---
name: voxpilot-verify
description: Explains how to execute the verification suite, tests, benchmarks, and gate checks for VoxPilot.
---

# VoxPilot Verification Skill

Use this skill when verifying milestones or checking performance and contracts.

## Key Verification Commands
- `.\scripts\verify.ps1`: Run full build, unit tests, integration tests, and budget checks.
- `python -m pytest tests/`: Run python test suite if python engine components are used.
- `dotnet test`: Run .NET test suite if C# solution is built.
- `.\bench\run_benchmarks.ps1`: Run STT and latency benchmarks.
