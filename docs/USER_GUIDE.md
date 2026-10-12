# VoxPilot User Guide: Complete Manual for Hands-Free Windows Control

**Version:** 1.0.0  
**Target Platform:** Windows 11 / Windows 10 (Build 19041+)  
**Security & Privacy:** Offline-First by Default, Zero External Telemetry  

---

## 1. Introduction & Overview

**VoxPilot** is a production-grade, hands-free voice control and dictation application designed specifically for Windows. It provides full computer control without touching a keyboard or mouse:
- **Click by Number:** Labels every interactive button, menu item, link, and control on your screen with numbered badges. Simply say the number to click it instantly.
- **Recursive Screen Grid:** Divides any screen into a 3x3 numbered grid (1–9). Say a number to subdivide that region recursively, allowing pixel-accurate mouse clicks anywhere on any display.
- **Natural Voice Dictation:** High-accuracy offline dictation featuring spoken punctuation expansion, NATO phonetic spelling, automatic formatting for currency and percentages, and atomic voice editing ("scratch that", "delete last word").
- **Window & System Automation:** Snap windows to screen edges, switch between open applications, navigate virtual desktops, and execute arbitrary keyboard chords by voice.
- **Browser DOM Integration:** Bundled Chromium extension for Chrome, Edge, and Brave provides complete element numbering on web pages where standard Windows accessibility trees are thin.
- **100% Local & Private:** All audio processing, speech recognition, and automation logic runs locally on your computer. Your voice never leaves your device.

---

## 2. Installation & Quick Setup

### 2.1 System Requirements
- **OS:** Windows 11 (all builds) or Windows 10 (Build 19041+)
- **CPU:** Intel Core i3 / AMD Ryzen 3 or newer (x86_64)
- **RAM:** 4 GB minimum (VoxPilot uses ~240 MB)
- **Microphone:** Built-in laptop microphone array or external USB/Bluetooth headset
- **Runtime:** Python 3.10+ (included in portable release bundle)

### 2.2 First-Time Diagnostics
Before running VoxPilot for the first time, run the built-in self-diagnostic doctor:
```powershell
.\voxpilot-doctor.bat
# or via command prompt:
python -m voxpilot.app.cli doctor
```

The Doctor verifies:
1. Windows build version and process elevation status.
2. Default WASAPI audio recording device and sample rate.
3. Offline Vosk acoustic models and Kaldi recognition graphs.
4. Display geometry, per-monitor DPI scaling, and multi-monitor bounds.
5. Windows UI Automation (UIA) tree accessibility on your active desktop.

---

## 3. Microphone Setup & Calibration Wizard

Accurate speech recognition requires clear audio input and an appropriate input gain. VoxPilot includes an automated calibration wizard.

To launch the wizard:
```powershell
python -m voxpilot.app.cli calibrate
```

The wizard performs two sequential checks:
1. **Ambient Noise Floor Measurement:**
   - Measures background room noise for 3.0 seconds while you remain silent.
   - Computes RMS audio energy and dBFS signal level.
   - Recommended noise floor: Below -40 dBFS. If noise exceeds -30 dBFS, VoxPilot will advise moving to a quieter space or reducing mic gain in Windows Sound Settings.
2. **Reading Sentence Verification (WER Check):**
   - Prompts you to speak a standard phonetic sentence:  
     `"the quick brown fox jumps over the lazy dog and clicks number twelve"`
   - Compares the speech engine's recognized text against the reference prompt to compute Word Error Rate (WER).
   - If WER is 0%, calibration passes with green status.

---

## 4. System Tray Controller & HUD Toast Bar

When you start VoxPilot (`.\voxpilot.bat`), it docks into your Windows system notification area (system tray):

### 4.1 Status Indicator
The tray icon and HUD reflect three operational modes:
- `[LISTENING]` (Green): Command mode active. VoxPilot is actively listening for navigation, numbering, grid, and window directives.
- `[DICTATION]` (Blue): Dictation mode active. VoxPilot streams spoken text directly into the focused input field.
- `[SLEEP]` (Gray): Asleep. Microphone listening is suspended. Say `"voxpilot wake up"` to resume.

### 4.2 Floating HUD Toast Bar
A lightweight, transparent HUD pill appears in the top-right corner of your primary display:
- Displays your current active mode (`[COMMAND]`, `[DICTATION]`, `[SLEEP]`).
- Renders live partial speech hypotheses in real-time as you speak.
- Shows execution feedback (e.g. `"Clicked #12 (Submit)"`, `"Switched to Dictation mode"`, `"Action blocked: Password field"`).

---

## 5. Screen Numbering (Click by Number)

VoxPilot numbers every interactive control on the active window or full screen.

### 5.1 Activating & Dismissing Numbers
- Say: `"show numbers"` (or `"please show numbers"`, `"numbers on"`)
  - VoxPilot scans the active window's UI Automation tree and paints amber badge overlays with bold numbers over every clickable control.
- Say: `"hide numbers"` (or `"numbers off"`, `"hide the numbers"`)
  - Dismisses all badges.

### 5.2 Clicking Elements
- Say: `"12"` or `"twelve"` or `"click 12"` or `"click twelve"`
  - Clicks element #12 immediately. Unlike Windows 11 Voice Access, VoxPilot requires **no confirmation step** ("OK"), saving clicks and reducing voice fatigue.
- Say: `"double click 5"`
  - Synthesizes a double-click on element #5.
- Say: `"right click 7"`
  - Opens the context menu for element #7.

### 5.3 Clicking by Spoken Name
If an element has an obvious label (e.g. a "Save" button), you can click it directly by name:
- Say: `"click save"` or `"click file"`
  - VoxPilot uses fuzzy matching to identify the button and clicks its center point.

---

## 6. Recursive Screen Grid (Pixel-Accurate Mouse Navigation)

For custom-drawn controls, canvas-based applications, maps, and games where UI Automation trees are absent, use the **Screen Grid**.

### 6.1 Activating the Grid
- Say: `"show grid"` (or `"grid on"`, `"show me the screen grid"`)
  - Overlays a 3x3 transparent grid dividing your screen into cells numbered 1 through 9.

### 6.2 Recursive Drill-Down
- Say: `"drill down 5"` or `"zoom into 5"`
  - Cell 5 is subdivided into 9 smaller numbered sub-cells.
- Say: `"drill down 3"`
  - Further subdivides that region. You can drill down up to 10 levels deep to target individual pixels.

### 6.3 Clicking Coordinates
- Say: `"4"` or `"click 4"`
  - Clicks the exact center of cell 4 and automatically closes the grid overlay.

### 6.4 Undoing Grid Steps
- Say: `"undo grid"` or `"zoom out"` or `"back"`
  - Steps back up one level in the grid hierarchy.
- Say: `"hide grid"` or `"cancel grid"`
  - Dismisses the grid without clicking.

---

## 7. Natural Voice Dictation & Text Editing

To dictate text into any document, text editor, email, or chat box:
1. Click into or focus the desired text field.
2. Say: `"start dictation"` (or `"dictate"`, `"dictation mode"`).
3. Begin speaking naturally.

### 7.1 Automatic Punctuation & Formatting
VoxPilot automatically expands spoken punctuation into standard symbols:
- `"hello world period"` -> `Hello world.`
- `"are you ready question mark next line"` -> `Are you ready?` (followed by a newline)
- `"send dollar 150 to account comma please"` -> `Send $150 to account, please`
- `"increased by 25 percent"` -> `Increased by 25%`
- `"release date is january 15 2026"` -> `Release date is January 15, 2026`
- `"user at example dot com"` -> `user@example.com`
- `"open https colon slash slash github dot com"` -> `Open https://github.com`
- `"read file dot json"` -> `Read file.json`

### 7.2 NATO Phonetic Spelling Mode
For acronyms, code identifiers, license keys, and unusual names:
- Say: `"spell alpha bravo charlie"` -> Types `ABC`
- Say: `"spell delta echo fox"` -> Types `DEF`

### 7.3 Spoken Editing Directives
Edit your text entirely by voice without touching the keyboard:
- `"scratch that"` (or `"delete that"`, `"undo that"`): Removes the entire preceding spoken text burst.
- `"delete last word"`: Removes the previous word.
- `"delete line"`: Deletes the current line.
- `"select all"`: Selects all text in the focused field (Ctrl+A).
- `"copy that"`: Copies the current selection to clipboard (Ctrl+C).
- `"paste that"`: Pastes from clipboard (Ctrl+V).
- `"cut that"`: Cuts selected text to clipboard (Ctrl+X).
- `"go to start of line"`: Moves cursor to beginning of line (Home).
- `"go to end of line"`: Moves cursor to end of line (End).
- `"stop dictation"`: Returns VoxPilot to Command Mode.

### 7.4 Security & Password Protection
VoxPilot strictly respects Windows security boundaries:
- If your cursor moves into a password input (`ES_PASSWORD` or ARIA password role), dictation is **blocked immediately**.
- If Windows locks or displays a UAC elevation prompt (Secure Desktop), all voice synthesis is frozen until you return to the interactive desktop.

---

## 8. Window, Application & Keyboard Commands

Control your Windows desktop layout and running applications:

| Action | Spoken Voice Phrase | Shortcut Injected |
|---|---|---|
| **Snap Left** | `"snap left"` / `"snap window left"` | Win + Left Arrow |
| **Snap Right** | `"snap right"` / `"snap window right"` | Win + Right Arrow |
| **Maximize** | `"maximize window"` / `"maximize"` | Win + Up Arrow |
| **Minimize** | `"minimize window"` / `"minimize"` | Win + Down Arrow |
| **Close Window** | `"close window"` / `"close app"` | Alt + F4 |
| **Switch App** | `"switch app"` / `"alt tab"` | Alt + Tab |
| **Task View** | `"task view"` | Win + Tab |
| **Next Desktop** | `"next desktop"` | Win + Ctrl + Right Arrow |
| **Previous Desktop**| `"previous desktop"` | Win + Ctrl + Left Arrow |
| **Page Down** | `"page down"` / `"scroll down"` | Page Down / Mouse Wheel Down |
| **Page Up** | `"page up"` / `"scroll up"` | Page Up / Mouse Wheel Up |

### 8.1 Keyboard Chords & Repeats
- **Chords:** Say `"press ctrl shift t"` to reopen a closed browser tab, or `"press alt f4"` to close an app.
- **Repeats:** Say `"press down 5 times"` or `"press tab 3 times"` to repeat a navigation key automatically.

---

## 9. Custom Commands & User Macros

You can define your own custom voice commands by editing `custom_commands.yaml` in your VoxPilot user directory (`%LOCALAPPDATA%\VoxPilot\custom_commands.yaml`):

```yaml
commands:
  - phrase: "open developer terminal"
    action: "hotkey"
    keys: ["win", "r"]

  - phrase: "insert my signature"
    action: "text"
    text: "Best regards,\nAlex Mercer\nLead Systems Architect"

  - phrase: "reopen last tab"
    action: "hotkey"
    keys: ["ctrl", "shift", "t"]
```

### Safety Guardrails
For system safety, VoxPilot strictly rejects dangerous command invocations (such as `rmdir`, `del`, `format`, `shutdown`, or encoded PowerShell commands).

---

## 10. Chromium & Edge Browser Extension Setup

For optimal web browsing on dynamic single-page applications:
1. Open Google Chrome, Microsoft Edge, or Brave.
2. Navigate to `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode** toggle in the top-right corner.
4. Click **Load unpacked** and browse to `extensions/chromium` inside your VoxPilot directory.
5. In an elevated PowerShell terminal, run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\installer\install_native_host.ps1
   ```
6. The extension communicates over standard Chromium Native Messaging, giving VoxPilot direct access to DOM clickable elements, links, and buttons.

---

## 11. Troubleshooting & Diagnostics

| Symptom | Cause | Solution |
|---|---|---|
| VoxPilot says `"No labeled element with number X"` | The window layout changed or the element closed | Say `"show numbers"` to refresh badge numbers. |
| Microphone not hearing commands | Default recording device misconfigured or muted | Run `python -m voxpilot.app.cli doctor` to inspect audio devices; run Windows Sound Settings to ensure mic is not muted. |
| Numbers overlay not appearing over Admin app | UIPI privilege isolation boundary | VoxPilot is running as standard user. To control elevated admin tools, launch VoxPilot as Administrator. |
| Voice typing blocked | Password field or Windows lock screen | Focus a standard text field and ensure Windows workstation is unlocked. |
| Web elements not numbered in Chrome | Chrome accessibility tree not initialized | Install the VoxPilot Chromium extension or run `install_native_host.ps1`. |

---

## 12. Privacy Policy & Offline Guarantee

- **Zero External Telemetry:** VoxPilot creates zero outbound network sockets. No user data, transcripts, or telemetry are transmitted.
- **Audio Never Leaves PC:** Speech recognition is executed locally via offline Vosk models.
- **Zero Audio on Disk:** Audio buffers reside only in transient memory during recognition and are discarded immediately.
