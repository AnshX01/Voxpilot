# VoxPilot Troubleshooting Guide

**Version:** 1.0.0  
**Target Platform:** Windows 11 / Windows 10 (Build 19041+)  

---

## 1. Quick Diagnostics First: `voxpilot doctor`

Before manual debugging, always run the automated diagnostic doctor:
```powershell
.\voxpilot-doctor.bat
# or
python -m voxpilot.app.cli doctor
```

The Doctor verifies:
- OS version and whether process is running elevated or standard.
- Audio input devices, sample rates, and default recording device.
- Offline Vosk acoustic model presence.
- Display bounds, monitor count, and DPI scale factors.
- Windows UI Automation accessibility tree responsiveness.

---

## 2. Audio & Microphone Issues

### 2.1 "No speech detected" or VoxPilot is not hearing commands
- **Symptom:** You speak commands, but nothing appears in the HUD toast bar and no action is executed.
- **Cause 1: Default microphone mismatch:**
  - Windows might have multiple audio capture endpoints (e.g. laptop array, virtual cables, Bluetooth headsets).
  - **Fix:** Open **Windows Settings -> System -> Sound -> Input**. Select your active microphone under "Choose your input device". Run `python -m voxpilot.app.cli doctor` to confirm the selected mic name.
- **Cause 2: Windows Microphone Privacy Permission:**
  - Windows 11 privacy settings may block desktop apps from accessing the microphone.
  - **Fix:** Open **Windows Settings -> Privacy & security -> Microphone**. Toggle **"Microphone access"** to **ON**, and ensure **"Let desktop apps access your microphone"** is set to **ON**.
- **Cause 3: High Ambient Background Noise:**
  - Excessive room noise (fans, air conditioning, TV, chatter) can degrade VAD energy detection.
  - **Fix:** Run the calibration wizard:
    ```powershell
    python -m voxpilot.app.cli calibrate
    ```
    Ensure the ambient noise floor is below -40 dBFS. Lower the microphone boost/gain in Windows Sound Settings if clipping occurs.

---

## 3. Overlay & Window Interaction Issues

### 3.1 Badges do not appear over an Administrator / Elevated Application
- **Symptom:** When focusing Task Manager, Command Prompt (Run as Administrator), or elevated installers, `"show numbers"` does not display badges or clicks are rejected.
- **Cause: User Interface Privilege Isolation (UIPI):**
  - Windows security prevents standard-user processes from synthesizing inputs into elevated processes.
  - **Fix:** If you need to control elevated administrative tools, launch VoxPilot itself as Administrator:
    - Right-click `voxpilot.bat` or `python` shortcut -> **Run as Administrator**.

### 3.2 Overlays do not show in Exclusive Full-Screen Games
- **Symptom:** Overlays fail to render over a full-screen 3D video game.
- **Cause:** Games using Exclusive Fullscreen Mode bypass the Desktop Window Manager (DWM) composition pipeline.
- **Fix:** Set the game's display settings from **"Exclusive Fullscreen"** to **"Borderless Windowed"** or **"Windowed Fullscreen"**. VoxPilot's transparent layered canvas will render seamlessly over borderless windows.

### 3.3 Elements are numbered with wrong coordinates on Mixed-DPI Displays
- **Symptom:** Badge pills appear offset by a few pixels on a secondary monitor with a different DPI scaling (e.g. 150% on laptop vs 100% on external monitor).
- **Fix:** Ensure VoxPilot is running with Per-Monitor V2 DPI awareness. VoxPilot's application manifest and Qt canvas automatically register `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`. If running from Python command line, confirm Windows display scaling is applied.

---

## 4. Web Browsing & Chromium / Edge Issues

### 4.1 Buttons and links inside Chrome / Edge / Brave are not numbered
- **Symptom:** `"show numbers"` numbers the browser window frame (tabs, address bar), but web page content inside the browser canvas has no numbers.
- **Cause 1: Chromium Accessibility Not Initialized:**
  - Chromium browsers disable their internal accessibility tree until requested to conserve battery and CPU.
  - **Fix:** VoxPilot automatically sends `WM_GETOBJECT` to activate Chromium's accessibility engine. Alternatively, launch Chrome with `--force-renderer-accessibility`.
- **Cause 2: Native Messaging Host Not Registered:**
  - The VoxPilot browser extension requires native messaging host registration.
  - **Fix:** Run the registration script in PowerShell:
    ```powershell
    powershell -ExecutionPolicy Bypass -File .\installer\install_native_host.ps1
    ```
  - Open `chrome://extensions`, verify the VoxPilot extension is enabled, and reload the web page.

---

## 5. Dictation & Voice Text Editing

### 5.1 Voice typing blocked with "Password field" warning
- **Symptom:** Speaking text produces a warning: `"Voice text injection blocked: focused control is a password field"`.
- **Cause:** Security feature. VoxPilot inspects Win32 `ES_PASSWORD` styles and UIA password traits to prevent voice leakage of credentials.
- **Fix:** Click or focus a standard text input field (such as Notepad, browser text area, or document body) before dictating.

### 5.2 Text typed in the wrong window
- **Symptom:** Spoken dictation burst lands in a different window if focus shifted mid-speech.
- **Fix:** VoxPilot implements focus target re-verification immediately before injecting Unicode text bursts. Ensure you do not Alt-Tab or click outside the text box while speaking.

---

## 6. Emergency Kill Switch

If an input sequence runs out of control or an overlay becomes visually stuck:
- **Global Hotkey:** Press **Ctrl + Alt + Shift + Escape** to immediately dismiss all overlays and release all logically held modifier keys.
- **CLI Reset:** In a terminal, run:
  ```powershell
  python -m voxpilot.app.cli say "go to sleep"
  ```
