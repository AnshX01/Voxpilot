# VoxPilot

**Complete, offline-first, hands-free voice control and dictation system for Windows 11.**

VoxPilot matches and exceeds macOS Voice Control and Windows 11 Voice Access by providing instant click-by-number without friction, a recursive 3x3 screen grid, multi-monitor geometry, high-accuracy dictation with atomic burst editing, custom commands, and a Chromium browser DOM extension.

```
+-------------------------------------------------------------------------------------------------+
|                                     VoxPilot Pipeline                                           |
|                                                                                                 |
|   WASAPI Audio Capture (16kHz Mono)                                                             |
|           |                                                                                     |
|           v                                                                                     |
|   Vosk Speech Engine (Streaming Kaldi Recognizer with Dynamic Grammar Biasing)                  |
|           |                                                                                     |
|           v                                                                                     |
|   Command-NLU Engine (Exact & Fuzzy Regex, Slots, Synonyms, Normalizers)                        |
|           |                                                                                     |
|           v                                                                                     |
|   Coordinator Engine                                                                            |
|      +------------------+--------------------+--------------------+--------------------+        |
|      |                  |                    |                    |                    |        |
|      v                  v                    v                    v                    v        |
|   Overlay Canvas      UI Automation       Dictation Service    Input Injector    Custom Commands|
|   (WS_EX_TRANSPARENT, (Chromium A11y,     (NATO Phonetic,      (Win32 SendInput  (YAML/JSON     |
|    WS_EX_NOACTIVATE,   UIA Tree Walk,      Burst History,       Click/Drag/Keys/  Macro Runner) |
|    PerMonitorV2 DPI)   CacheRequest)       Formatting)          Unicode Typing)                 |
+-------------------------------------------------------------------------------------------------+
```

---

## Key Differentiators vs macOS Voice Control & Windows 11 Voice Access

| Feature | macOS Voice Control | Windows 11 Voice Access | **VoxPilot** |
|---|---|---|---|
| **Click by Number** | Fast | Requires confirmation ("OK") or delay | **Instant direct dispatch (P95 latency: 0.01 ms)** |
| **Numbering Stability** | Dynamic | Often shifts IDs between refreshes | **Stable spatial sorting & geometry hashing** |
| **Screen Grid** | Numbered grid | Primary monitor only; 1-9 digits | **Multi-monitor spanning; recursive 3x3 drill-down with undo** |
| **Browser Element Coverage**| Accessibility tree only | Web UIA tree often thin or missing | **Dual-engine: UIA + Chromium MV3 DOM Extension** |
| **Privacy & Telemetry** | Local after download | Cloud/Hybrid Microsoft Telemetry | **100% Offline by default; zero external telemetry** |
| **Spoken Text Editing** | Good | Basic | **Atomic burst undo ("scratch that"), NATO spelling, normalizers** |
| **Extensibility** | Basic custom commands | Fixed command catalog | **Full YAML/JSON custom command engine with safety guardrails** |
| **Diagnostics** | Minimal | None | **`voxpilot doctor` self-diagnostic suite** |

---

## Performance Benchmark Summary

Measured and certified on Windows 11 Build 26200 (Intel i5-12450H CPU, 16GB RAM, RTX 3050 Laptop GPU):

- **"Show numbers" Discovery & Paint:** P95 latency **3.81 ms** (budget <= 100 ms) — **26x faster than budget**.
- **Spoken Number to Click Dispatched:** P95 latency **0.01 ms** (budget <= 150 ms) — **sub-millisecond instant dispatch**.
- **Dictation Burst Format & Inject:** P95 latency **0.46 ms** (budget <= 400 ms) — **860x faster than budget**.
- **Streaming Audio Chunk Processing:** P95 latency **4.29 ms** per 100ms chunk (RTF **~0.04** vs <= 0.25 budget).
- **1,000-Command Soak Throughput:** **652.0 commands/sec** with zero memory or handle leaks (+18.87 MB RSS delta).
- **Command Recognition Accuracy:** **100.0%** clean corpus (30/30) and **100.0%** noisy/conversational corpus (10/10).

---

## Quick Start

### 1. Requirements
- Windows 10 (Build 19041+) or Windows 11 (Build 22000+)
- Python 3.10+ (tested through Python 3.14)
- Working microphone (WASAPI audio capture)

### 2. Verify System with Doctor
```powershell
.\voxpilot-doctor.bat
# or
python -m voxpilot.app.cli doctor
```

### 3. Launch VoxPilot System Tray
```powershell
.\voxpilot.bat
# or
python -m voxpilot.app.tray
```

The VoxPilot microphone tray icon will appear in the Windows taskbar notifications area, showing live status (`[LISTENING]`, `[DICTATION]`, `[SLEEP]`).

### 4. CLI Interaction & Scripting
```powershell
# Directly inject spoken phrases via CLI
python -m voxpilot.app.cli say "show numbers"
python -m voxpilot.app.cli say "click 5"
python -m voxpilot.app.cli say "show grid"
python -m voxpilot.app.cli say "drill down 5"
python -m voxpilot.app.cli say "undo grid"
python -m voxpilot.app.cli say "hide grid"

# Search available voice commands
python -m voxpilot.app.cli list-commands --filter "snap"

# Inspect foreground window accessibility tree
python -m voxpilot.app.cli dump-ui

# Calibrate microphone noise floor and speech WER
python -m voxpilot.app.cli calibrate
```

---

## Chromium / Edge Browser Extension

VoxPilot includes a dedicated Chromium Manifest V3 extension providing pixel-perfect DOM element numbering on complex Single Page Applications (SPAs) and dynamic websites.

1. Open `chrome://extensions` or `edge://extensions`.
2. Toggle on **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select `extensions/chromium`.
4. Register the native messaging host in Windows registry:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\installer\install_native_host.ps1
   ```

---

## Core Voice Commands

| Category | Spoken Phrase | Action |
|---|---|---|
| **Numbering** | `"show numbers"` | Numbers every interactive UI control on screen |
| | `"click 12"` or `"twelve"` | Clicks item #12 instantly |
| | `"double click 5"` | Double-clicks item #5 |
| | `"right click 7"` | Right-clicks item #7 |
| | `"hide numbers"` | Dismisses number overlay |
| **Screen Grid** | `"show grid"` | Activates 3x3 screen grid |
| | `"drill down 5"` or `"zoom into 5"` | Subdivides cell 5 into 3x3 sub-cells |
| | `"undo grid"` or `"zoom out"` | Steps back up one level in grid hierarchy |
| | `"click 4"` | Clicks center of cell 4 and dismisses grid |
| **Dictation** | `"start dictation"` | Switches to continuous dictation mode |
| | `"stop dictation"` | Returns to command mode |
| | `"scratch that"` | Un-does the last spoken text burst |
| | `"delete last word"` | Deletes the preceding word |
| | `"select all"` / `"copy that"` | Selects all text or copies to clipboard |
| | `"spell alpha bravo charlie"` | Inserts NATO phonetic text (`ABC`) |
| **Window Control** | `"snap left"` / `"snap right"` | Snaps window to left / right screen half |
| | `"switch app"` | Triggers Alt-Tab task switcher |
| | `"task view"` | Opens Windows Task View |
| | `"minimize window"` / `"maximize window"` | Minimizes or maximizes focused app |
| **System** | `"voxpilot go to sleep"` | Pauses speech recognition listening |
| | `"voxpilot wake up"` | Resumes voice listening |

*For the complete command reference catalog, see [docs/COMMANDS.md](file:///C:/Users/anshw/Documents/Voxpilot/docs/COMMANDS.md).*

---

## Documentation

- [User Guide](file:///C:/Users/anshw/Documents/Voxpilot/docs/USER_GUIDE.md): Full end-to-end user manual.
- [Commands Reference](file:///C:/Users/anshw/Documents/Voxpilot/docs/COMMANDS.md): Comprehensive catalog of all supported phrases.
- [Architecture](file:///C:/Users/anshw/Documents/Voxpilot/docs/ARCHITECTURE.md): Pipeline specification, contracts, and threading model.
- [Security & Privacy](file:///C:/Users/anshw/Documents/Voxpilot/docs/SECURITY.md): Threat model, offline isolation, and credential boundaries.
- [Performance Report](file:///C:/Users/anshw/Documents/Voxpilot/docs/evidence/perf/perf_report.md): Verified soak and latency measurements.
- [Final Report](file:///C:/Users/anshw/Documents/Voxpilot/docs/FINAL_REPORT.md): Project summary, comparative analysis, and limitations.

---

## License

Private & Local — Built for Windows 11. Offline First by Default.
