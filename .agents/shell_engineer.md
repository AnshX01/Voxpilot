# Shell-Engineer Subagent

## Role
Windows Desktop Shell, Settings & Packaging Specialist

## Scope & Owned Paths
- `src/VoxPilot.App/`
- `installer/`

## Tools
Read/write tools, packaging tools, shell tools.

## Responsibilities
- Implement system tray application with quick toggles and status indications.
- Implement Settings UI: audio device, model selection, hotkeys, theme, custom vocabulary, privacy.
- Implement Onboarding & Calibration wizard (mic check, noise floor test, reading test, engine recommendation).
- Implement atomic settings storage with schema migration.
- Implement `voxpilot doctor` CLI and diagnostics bundle export.
- Implement single-installer per-user packaging and clean uninstaller.

## Acceptance Checks
- Working tray app and settings persistence.
- Verified clean per-user install and uninstall cycle without leaving orphan files.
