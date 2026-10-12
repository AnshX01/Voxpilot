# VoxPilot Custom Commands & Macro Authoring Guide

VoxPilot allows users to define custom voice commands to automate repetitive workflows, insert boilerplate text, trigger keyboard shortcuts, and launch external tools.

---

## 1. Configuration File Location

Custom commands can be defined in YAML or JSON format. By default, VoxPilot looks for:
- YAML: `%LOCALAPPDATA%\VoxPilot\custom_commands.yaml`
- JSON: `%LOCALAPPDATA%\VoxPilot\custom_commands.json`
- Project root fallback: `custom_commands.yaml`

---

## 2. Configuration Schema

A custom commands file consists of a top-level `commands` array:

```yaml
commands:
  - phrase: "spoken voice trigger phrase"
    action: "hotkey" | "text" | "command"
    # Additional action-specific fields...
```

### 2.1 Action Types

#### 1. `hotkey` (Keyboard Shortcut Synthesis)
Sends a key combination using Win32 `SendInput`:
```yaml
- phrase: "reopen closed tab"
  action: "hotkey"
  keys: ["ctrl", "shift", "t"]

- phrase: "open windows settings"
  action: "hotkey"
  keys: ["win", "i"]

- phrase: "lock my workstation"
  action: "hotkey"
  keys: ["win", "l"]
```

Supported key names:
- Modifiers: `ctrl`, `shift`, `alt`, `win`
- Navigation: `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`
- Editing: `enter`, `escape`, `tab`, `backspace`, `delete`, `space`
- Function keys: `f1` through `f12`
- Alphanumeric: `a` through `z`, `0` through `9`

#### 2. `text` (Boilerplate Text Injection)
Types a block of Unicode text into the currently focused text field:
```yaml
- phrase: "insert my signature"
  action: "text"
  text: "Best regards,\nAlex Mercer\nStaff Systems Engineer"

- phrase: "insert meeting template"
  action: "text"
  text: "## Agenda\n1. Project Status\n2. Blockers\n3. Next Milestones\n"
```

#### 3. `command` (Executable Launching)
Launches a desktop executable or script:
```yaml
- phrase: "launch calculator"
  action: "command"
  command: "calc.exe"

- phrase: "open notepad"
  action: "command"
  command: "notepad.exe"
```

---

## 3. Safety Guardrails & Execution Policy

To protect the user's workstation, VoxPilot strictly validates command actions prior to execution. The following destructive primitives are **hard-blocked** and will be rejected with an error:
- File deletion commands: `rmdir`, `del`, `erase`, `rd`
- Disk management: `format`, `diskpart`
- System control: `shutdown`, `restart`, `taskkill /f`
- Obfuscated scripting: `powershell -enc`, `powershell -encodedcommand`, `powershell -e`
- Registry manipulation: `reg delete`, `reg add`

All external commands run with user permissions (never elevated) and enforce a strict execution timeout.

---

## 4. Complete Example `custom_commands.yaml`

```yaml
commands:
  # Browser Navigation
  - phrase: "duplicate tab"
    action: "hotkey"
    keys: ["ctrl", "k"]

  - phrase: "bookmark this page"
    action: "hotkey"
    keys: ["ctrl", "d"]

  # Developer Shortcuts
  - phrase: "format document"
    action: "hotkey"
    keys: ["shift", "alt", "f"]

  - phrase: "open terminal"
    action: "hotkey"
    keys: ["ctrl", "`"]

  # Text Snippets
  - phrase: "insert copyright"
    action: "text"
    text: "Copyright (c) 2026 VoxPilot Contributors. All rights reserved."

  # Tools
  - phrase: "open task manager"
    action: "command"
    command: "taskmgr.exe"
```
