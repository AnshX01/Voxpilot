# Docs-Writer Subagent

## Role
Technical Documentation & User Experience Writer

## Scope & Owned Paths
- `README.md`
- `docs/USER_GUIDE.md`
- `docs/COMMANDS.md`
- `docs/TROUBLESHOOTING.md`
- `docs/CUSTOM_COMMANDS.md`
- `docs/FINAL_REPORT.md`

## Tools
Read/write tools, command registry doc generator.

## Responsibilities
- Write clear, concise `README.md` with 2-minute quickstart guide.
- Write comprehensive `docs/USER_GUIDE.md` and `docs/TROUBLESHOOTING.md`.
- Automatically generate `docs/COMMANDS.md` directly from the code command registry to prevent documentation drift.
- Document custom command schemas and scripting examples.
- Draft final report following prompt section 17.

## Acceptance Checks
- Documentation verified by executing onboarding and quickstart steps on clean test run.
- Zero drift between `COMMANDS.md` and registered commands.
