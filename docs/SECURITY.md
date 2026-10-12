# VoxPilot Security, Privacy & Integrity Specification

**Date:** 2026-10-13  
**Auditor:** Security-Privacy-Reviewer  
**Status:** **VERIFIED & COMPLIANT (ZERO EXTERNAL TELEMETRY, OFFLINE-FIRST)**

---

## 1. Security Architecture & Threat Model

VoxPilot is built strictly according to **Offline First** and **Privacy by Default** principles. The application operates entirely within local machine boundaries without external server dependencies, cloud speech recognition, or diagnostic telemetry.

```
+--------------------------------------------------------------------------+
|                            USER WORKSTATION                              |
|                                                                          |
|  [WASAPI Capture] ---> [Local Memory Buffer] ---> [Local Vosk / Whisper] |
|                                                           |              |
|                                                           v              |
|  [UI Automation]  <--- [Dispatcher]           <--- [Command-NLU]         |
|         |                     |                                          |
|         v                     v                                          |
|  [Target App]         [Overlay Canvas]                                   |
|                                                                          |
|  NO NETWORK SOCKETS | NO CLOUD APIS | NO TELEMETRY | NO AUDIO ON DISK   |
+--------------------------------------------------------------------------+
```

---

## 2. Privacy & Telemetry Verification

### 2.1 Zero External Network Calls
- **Static Code Audit:** Full AST and regex audit across `src/voxpilot/` confirms zero usage of `requests`, `urllib.request`, `httpx`, `aiohttp`, `socket.connect`, or third-party telemetry libraries.
- **Dependency Isolation:** Runtimes (Vosk, OnnxRuntime, PySide6) are configured strictly in offline mode. Vosk acoustic models and Kaldi graphs are loaded exclusively from local disk (`models/vosk-model-small-en-us-0.15`).
- **Telemetry Policy:** VoxPilot contains zero product telemetry, error reporting beacons, analytics beacons, or remote update checks.

### 2.2 Audio Data Retention Policy
- **Zero Disk Persistence by Default:** Raw audio chunks captured from the microphone endpoint are passed directly into in-memory queues and processed in-process. Chunks are garbage-collected immediately following recognition.
- **Debug Trace Isolation:** Neither audio samples nor spoken transcripts are written to persistent storage unless the user explicitly enables `--debug-audio` via command-line flags. When active, a prominent persistent indicator is rendered in the HUD toast overlay.

---

## 3. Credential & Desktop Boundaries

### 3.1 Password Field Gating (`ES_PASSWORD` / ARIA Password)
- **Protection Mechanism:** Both `IContextService` and `DictationService` query the foreground control's Win32 window styles (`GetWindowLongPtr(GWL_STYLE) & ES_PASSWORD`) and UIA control properties (`IsPassword == True`).
- **Behavior:** When focus lands on a password input, voice dictation bursts are blocked with `BlockedReason.PASSWORD_FIELD`. No text injection occurs, and no keystrokes are synthesized.

### 3.2 Secure Desktop & Workstation Lock Protection
- **Desktop Isolation:** Windows isolates UAC elevation prompts and the Ctrl+Alt+Del lock screen into the `Winlogon` desktop. VoxPilot runs on the interactive user desktop (`WinSta0\Default`).
- **Protection Mechanism:** VoxPilot queries `OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)`. If desktop switching is detected (e.g. UAC prompt or Win+L lock screen), all input injection is halted immediately with `BlockedReason.SECURE_DESKTOP`.

### 3.3 User Interface Privilege Isolation (UIPI)
- **Elevation Boundary:** Standard-user processes in Windows cannot synthesize input (`SendInput`) into Administrator / elevated windows due to UIPI.
- **Handling:** When the user targets an elevated window, VoxPilot detects the integrity mismatch and returns `BlockedReason.UIPI` with a clear user-facing message, rather than hanging or silently failing.

---

## 4. Custom Command & Shell Injection Defense

### 4.1 Custom Command Execution Guardrails
User-defined macros in `custom_commands_loader.py` are strictly validated prior to execution:
- **Blocked Primitives:** Destructive commands including `rmdir`, `del`, `format`, `shutdown`, `taskkill /f`, `reg delete`, `diskpart`, and encoded PowerShell invocations (`powershell -enc`, `powershell -e`) are rejected with `BlockedReason.HIGH_RISK_COMMAND`.
- **Validation:** YAML/JSON schemas are strictly enforced to prevent arbitrary shell injection.

### 4.2 Chromium Native Messaging Security
- **Framing Protocol:** Implements length-prefixed 32-bit unsigned integer framing conforming to Chromium Native Messaging specs.
- **Buffer Overflow Protection:** Message lengths exceeding 1MB are rejected to prevent heap allocation attacks (adversarially tested up to 100MB).
- **Origin Validation:** Native host manifest `com.voxpilot.host.json` restricts allowed origins to the specific unpacked extension ID.

---

## 5. Security Audit Checklist

| Security Control | Verification Method | Status |
|---|---|---|
| Outbound Network Isolation | Static analysis & network socket audit | **VERIFIED (0 sockets)** |
| Zero Audio Logging | Filesystem inspection during FakeMic & live runs | **VERIFIED (0 bytes saved)** |
| Password Field Gating | `test_password_field_focus_gating` in `test_fault_injection.py` | **VERIFIED (PASSED)** |
| Secure Desktop Gating | `test_secure_desktop_lock_workstation` in `test_fault_injection.py` | **VERIFIED (PASSED)** |
| Destructive Command Rejection | `test_custom_command_loader` in `test_extended_commands.py` | **VERIFIED (PASSED)** |
| Native Host Framing Boundary | `test_adversarial_round2.py` (100MB attack) | **VERIFIED (PASSED)** |
| Non-destructive System Behavior | No registry edits outside VoxPilot root, no driver installs | **VERIFIED (PASSED)** |

---

## 6. Auditor Sign-Off

VoxPilot satisfies all security, privacy, and integrity requirements. The architecture provides complete confidentiality for user voice data and robust resistance to privilege escalation and command injection.
