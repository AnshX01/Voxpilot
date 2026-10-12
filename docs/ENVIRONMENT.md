# VoxPilot System Environment Specification

Verified on host: **DESKTOP-ANSHX**  
Date of Discovery: **October 12, 2026**  
Recon Specialist Agent: **Recon**  

---

## 1. Operating System & Platform

| Attribute | Value | Verification Source |
|---|---|---|
| **OS Name** | Microsoft Windows 11 Home Single Language | `Win32_OperatingSystem.Caption` |
| **OS Version** | 10.0.26200 | `Win32_OperatingSystem.Version` |
| **Display Version** | 25H2 | `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\DisplayVersion` |
| **Build Number** | 26200 | `CurrentBuildNumber` |
| **UBR (Update Revision)** | 9457 (Full Build: `26200.9457`) | `HKLM:\...\CurrentVersion\UBR` |
| **Architecture** | 64-bit (x86_64 / AMD64) | `Win32_OperatingSystem.OSArchitecture` |
| **Edition ID** | CoreSingleLanguage | Registry `EditionID` |
| **System Locale (User)** | `en-IN` (English - India, LCID 16393) | `Get-Culture` |
| **UI Display Language** | `en-GB` (English - UK, LCID 2057) | `Get-UICulture` |
| **Language Features** | `en-GB` (BasicTyping, Handwriting, Speech, TTS, OCR)<br>`en-IN` (BasicTyping, Speech, TTS)<br>`en-US` (BasicTyping, Handwriting, OCR) | `Get-InstalledLanguage` |

---

## 2. Hardware Architecture

### 2.1 Processor (CPU)
- **Model:** 12th Gen Intel(R) Core(TM) i5-12450H
- **Manufacturer:** GenuineIntel (Alder Lake Architecture)
- **Cores / Threads:** 8 physical cores (4 Performance-cores + 4 Efficient-cores), 12 logical processors
- **Base / Max Clock:** 2.00 GHz base, up to 4.40 GHz Max Turbo
- **Instruction Sets:** AVX2, FMA3, SSE4.2, Intel DL Boost (VNNI) supported.

### 2.2 System Memory (RAM)
- **Total Physical RAM:** 16,437,400 KB (~15.68 GB visible / 16.0 GB hardware)
- **Free Physical RAM:** 8,874,544 KB (~8.46 GB available during benchmark)
- **Total Virtual Memory:** 25,874,584 KB (~24.68 GB)
- **Free Virtual Memory:** 17,136,816 KB (~16.34 GB)

### 2.3 Storage (Disks)
- **Drive C: Total Space:** 510,694,256,640 bytes (475.61 GB)
- **Drive C: Free Space:** 180,359,979,008 bytes (167.97 GB free, 35.3% free)
- **File System:** NTFS

### 2.4 Graphics & Compute Accelerators (GPU / NPU)
- **Discrete GPU:**
  - **Model:** NVIDIA GeForce RTX 3050 Laptop GPU
  - **Dedicated VRAM:** 4,293,918,720 bytes (4096 MiB / 4.0 GB GDDR6)
  - **Driver Version:** 32.0.16.1692 (NVIDIA Driver 616.92)
  - **Driver Model:** WDDM 3.2
  - **CUDA UMD Version:** 13.4
  - **Bus ID:** `00000000:01:00.0`
- **Integrated GPU:**
  - **Model:** Intel(R) UHD Graphics (Family: Alder Lake-P 64EU)
  - **Driver Version:** 32.0.101.5542
  - **Adapter RAM:** 2,147,479,552 bytes (shared memory)
- **Neural Processing Unit (NPU):**
  - **Detected:** **None** (Intel 12th Gen Core i5-12450H does not feature an integrated NPU; verified via `Win32_PnPEntity` class `ComputeAccelerator`).
- **AI Acceleration Runtimes:**
  - **DirectX / Direct3D:** Direct3D 12 Feature Level 12_2 supported.
  - **DirectML:** Present at `C:\Windows\System32\DirectML.dll` (v1.15.5+250417-0100.1.os-germanium.7c460ce).
  - **CUDA:** NVIDIA CUDA Driver runtime supported (driver supports CUDA 13.4); CUDA Toolkit `nvcc` compiler not on system PATH.
  - **ONNX Runtime:** Python `onnxruntime` 1.28.0 installed with `AzureExecutionProvider` and `CPUExecutionProvider`. DirectML provider (`onnxruntime-directml`) can be added for hardware acceleration on both Intel UHD and RTX 3050.

---

## 3. Installed Runtimes & Development Toolchains

| Runtime / Tool | Status | Version / Path | Notes |
|---|---|---|---|
| **.NET SDK** | **Not Installed** | None on PATH or `Program Files\dotnet` | Windows contains standard .NET Framework 4.8 / CLR 4.0 |
| **Python** | **Installed** | `3.14.2` (`C:\Users\anshw\AppData\Local\Programs\Python\Python314\python.exe`) | Additional Python installations detected in registry: 3.10.0, 3.11.1 |
| **Python Pip** | **Installed** | `26.0.1` | Installed packages include: `torch` 2.13.0, `onnxruntime` 1.28.0, `PySide6` 6.11.2, `pywin32` 312, `transformers` 5.14.1 |
| **Node.js** | **Installed** | `v24.13.0` | `npm` available |
| **Git** | **Installed** | `2.52.0.windows.1` | Functional git repository |
| **MSVC / C++ Tools** | **Not Installed** | None (`vswhere`, `cl.exe`, `gcc` absent) | Visual C++ 2015-2022 Redistributable (x86 v14.51.36247) present |
| **winget** | **Installed** | `v1.29.380` | Functional Windows Package Manager |
| **Ollama** | **Installed** | `0.32.15` | Local LLM daemon available |
| **WSL 2** | **Installed** | `2.6.3.0` | Linux subsystem functional |

---

## 4. Audio Subsystem & Endpoints

### 4.1 WASAPI / Core Audio Endpoints
Verified via `IMMDeviceEnumerator` and `IAudioClient` native queries:

1. **Default Console & Multimedia Capture Endpoint (Primary Input):**
   - **Device Friendly Name:** `Microphone Array (Intel(R) Smart Sound Technology for Digital Microphones)`
   - **Endpoint ID:** `{0.0.1.00000000}.{97654149-1c1d-42c3-9284-7a9e10a9ee50}`
   - **Native Mix Format:** 48,000 Hz, 2 Channels (Stereo), 32-bit IEEE Float
   - **WinMM Support:** 0x000FFFFF (Full standard PCM range: 8 kHz to 96 kHz, 8/16-bit mono/stereo)
2. **Default Communications Capture Endpoint:**
   - **Device Friendly Name:** `Headset (ZEB-VITA BAR 150)`
   - **Endpoint ID:** `{0.0.1.00000000}.{082276a0-1a37-49f9-868f-87987b837861}`
   - **Native Mix Format:** 16,000 Hz, 1 Channel (Mono), 32-bit IEEE Float
3. **Other Capture Endpoints in Hardware Store:**
   - `Stereo Mix` (Realtek)
   - `Headset Microphone` (Unplugged)
   - `Microphone` (Realtek, NotPresent)

### 4.2 Microphone Privacy & Permissions
- **HKCU Privacy Consent:** `Allow` (`HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone`)
- **HKLM Privacy Consent:** `Allow` (`HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone`)
- **Implication:** Desktop capture and background WASAPI audio streams are unrestricted by OS permission barriers.

### 4.3 VoxPilot Audio Pipeline Implications
- Default capture is **48 kHz 32-bit float stereo**. Whisper / Speech models require **16 kHz 16-bit PCM mono**.
- The audio capture engine must implement a zero-allocation or ring-buffered resampling stage (48,000 Hz -> 16,000 Hz) and downmix stereo to mono.
- If communicating headset is selected, incoming stream is already 16,000 Hz mono (converting float32 -> int16 directly).

---

## 5. Display & Rendering Subsystem

Verified via `System.Windows.Forms.Screen`, `EnumDisplayDevices`, and Win32 Desktop API:

- **Active Attached Monitors:** 1 active monitor
- **Primary Monitor Device:** `\\.\DISPLAY5` (routed directly via NVIDIA GeForce RTX 3050 Laptop GPU)
- **Physical Panel:** Acer external monitor (`DISPLAY\ACR0E8C`, 53cm x 30cm, ~24" diagonal)
- **Resolution:** 1920 x 1080
- **Working Area:** 1920 x 1032 (48px standard taskbar)
- **Virtual Screen Bounds:** `{X=0, Y=0, Width=1920, Height=1080}`
- **System DPI:** 96 DPI (100% scale factor, `AppliedDPI = 96`)
- **Per-Monitor Scaling:** 1.0x (96 DPI)
- **Color Depth:** 32 bits per pixel

---

## 6. Target Application Inventory

| Target Application | Presence | Version | Executable / App Path |
|---|---|---|---|
| **Notepad** | Present | 10.0.26200.1 | `C:\Windows\System32\notepad.exe` |
| **Calculator** | Present | 11.2607.0.0 | `C:\Program Files\WindowsApps\Microsoft.WindowsCalculator_11.2607.0.0_x64__8wekyb3d8bbwe` |
| **File Explorer** | Present | 10.0.26200.9457 | `C:\Windows\explorer.exe` |
| **Microsoft Edge** | Present | 155.0.4283.45 | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` |
| **Brave Browser** | Present | 155.1.97.56 | `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe` |
| **Google Chrome** | Not Installed | - | None |
| **Mozilla Firefox** | Not Installed | - | None |
| **VS Code** | Present | 1.136.0 | `C:\Program Files\Microsoft VS Code\bin\code.cmd` |
| **Windows Terminal** | Present | 1.24.12741.0 | `C:\Program Files\WindowsApps\Microsoft.WindowsTerminal_1.24.12741.0_x64__8wekyb3d8bbwe` |
| **Microsoft Office** | Present | 16.0.20326.20158 | `C:\Program Files\Microsoft Office\root\Office16\` (`WINWORD.EXE`, `EXCEL.EXE`, `POWERPNT.EXE`) |

---

## 7. Security, Integrity & Permissions

- **Process Privilege Token:** Non-Elevated Standard User (`DESKTOP-ANSHX\anshw`).
- **Admin Elevation (`IsElevated`):** `False`.
- **Developer Mode:** **Disabled** (`HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock\AllowDevelopmentWithoutDevLicense` is not configured).
- **Implications for VoxPilot:**
  - Standard user execution guarantees that VoxPilot will operate cleanly in consumer/enterprise non-admin environments without requiring UAC escalation.
  - UI Automation (`UIAutomationClient`) can inspect and interact with all standard user desktop applications.
  - When target applications run elevated (e.g. Administrator Terminal), UI Automation cross-integrity barriers (UIPI - User Interface Privilege Isolation) will prevent SendInput / synthetic events unless VoxPilot is run with matching elevation or `uiAccess="true"`.
  - Windows overlay must use standard top-level transparent click-through windows (`WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_NOACTIVATE`).

---

## 8. Windows Built-In Voice Control Assessment

- **VoiceAccess Executable:** `C:\Windows\System32\VoiceAccess.exe` (File version 10.0.26100.8875).
- **Start Menu Shortcut:** `C:\Users\anshw\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Accessibility\VoiceAccess.lnk`.
- **Legacy SAPI Engine (`sapisvr.exe`):** Deprecated and removed in Windows 11 Build 26200.
- **Runtime Execution Status:** **Non-functional / Fails silently.**
  - Direct invocation of `VoiceAccess.exe` immediately exits with exit code 0 within ~100ms.
  - Binary inspection confirms `VoiceAccess.exe` is a lightweight bootstrap stub (`VoiceAccessStub.cpp`).
  - The stub requires packaged WinUI 3 dependencies (`WindowsUdk.UI.Shell.VoiceAccessExtension`), which fail to resolve.
  - Locale strings reveal hardcoded gating: *"Voice access works best with English (United States)"*, *"We can't start voice access Your device language was changed"*, *"Voice access is disabled"*.
  - Because current system culture is `en-IN` with `en-GB` display, Voice Access aborts without launching an interface or delivering user feedback.
- **Strategic Impact:** The machine currently has zero functional built-in voice accessibility. VoxPilot fills an urgent operational void.
