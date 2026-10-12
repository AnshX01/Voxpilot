# VoxPilot Project Rules & Agent Guidelines

## 1. Non-Negotiable Core Rules
1. **Evidence over claims:** Never declare any milestone complete without verified test execution, logs, latency numbers, or screenshots recorded under `docs/evidence/`.
2. **No fake work:** No stubs, mocks of core logic, dummy returns, or TODO implementations. Real working code only.
3. **Contracts first:** All modules adhere strictly to interfaces in `src/VoxPilot.Contracts/` (or equivalent python contracts if hybrid/python).
4. **Ownership:** One owner per path. Subagents must only edit files within their owned directories.
5. **Privacy & Offline First:** Zero external telemetry. Audio never leaves the machine. Works offline.
6. **Machine safety:** Safe execution; no destructive registry edits or system modifications.
7. **Append-Only Worklog:** Every action and milestone must be logged in `docs/WORKLOG.md`.

## 2. Directory Ownership Map
- `Recon`: `docs/ENVIRONMENT.md`, `docs/COMPETITIVE_NOTES.md`
- `Architect`: `docs/ARCHITECTURE.md`, `src/VoxPilot.Contracts/`
- `Speech-Engine`: `src/VoxPilot.Speech/`, `bench/stt/`
- `Command-NLU`: `src/VoxPilot.Commands/`
- `UIA-Engineer`: `src/VoxPilot.Automation/`
- `Overlay-UI`: `src/VoxPilot.Overlay/`
- `Input-Engineer`: `src/VoxPilot.Input/`
- `Dictation-Engineer`: `src/VoxPilot.Dictation/`
- `Browser-Ext`: `extensions/chromium/`, `src/VoxPilot.NativeHost/`
- `Shell-Engineer`: `src/VoxPilot.App/`, `installer/`
- `Test-Engineer`: `tests/`, `fixtures/`, `bench/`
- `Adversary`: `docs/evidence/adversarial/` (Bug reports to `docs/BUGS.md`)
- `Security-Privacy-Reviewer`: `docs/SECURITY.md`
- `Perf-Profiler`: `docs/evidence/perf/`
- `Docs-Writer`: `README.md`, `docs/USER_GUIDE.md`, `docs/COMMANDS.md`
- `Reviewer`: `docs/REVIEWS/`
