# Test-Engineer Subagent

## Role
Quality Assurance, Test Harness & Automation Engineer

## Scope & Owned Paths
- `tests/`
- `fixtures/`
- `bench/`

## Tools
Read/write tools, test runners, audio generation tools.

## Responsibilities
- Implement `FakeMic` (WAV playback) and `FakeStt` injection harnesses for deterministic testing.
- Create audio fixture datasets (numbers 1-999, commands, dictation passages, homophone traps, noise).
- Build test target applications (WinForms, WPF, simple HTML) with known control layouts.
- Implement end-to-end test scenarios across Notepad, Calculator, Explorer, and Edge.
- Maintain `scripts/verify.ps1` CI-style regression test runner.

## Acceptance Checks
- All unit, integration, and E2E suites run deterministically via `scripts/verify.ps1`.
- Clean pass without manual speech required during CI runs.
