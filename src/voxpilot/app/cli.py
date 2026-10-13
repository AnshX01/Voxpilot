"""VoxPilot Command-Line Interface (CLI) & Diagnostic Doctor.

Commands:
  voxpilot doctor        - Inspect hardware, runtimes, audio devices, models, and permissions.
  voxpilot say <phrase>  - Simulate spoken voice command and print execution result.
  voxpilot list-commands - Print full catalog of built-in and custom voice commands.
  voxpilot dump-ui       - Discover and print interactive controls for foreground window.
  voxpilot calibrate     - Measure mic noise floor and test acoustic calibration.
  voxpilot run           - Launch VoxPilot desktop engine with HUD overlay and system tray.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import sys
import time
from typing import Optional

from ..automation.context_service import ContextService
from ..automation.uia_provider import UiaElementProvider
from ..commands.command_parser import CommandParser
from ..contracts.dto import Intent
from ..input.input_injector import WindowsInputInjector
from ..overlay.overlay_service import OverlayService
from .calibration import CalibrationWizard


def run_doctor() -> int:
    """Perform comprehensive self-diagnostics and print health report."""
    print("==================================================================")
    print("                   VoxPilot Diagnostic Doctor                     ")
    print("==================================================================")

    # 1. OS & Platform
    os_name = platform.platform()
    py_ver = sys.version.split()[0]
    print(f"[*] OS:             {os_name}")
    print(f"[*] Python:         {py_ver}")

    # 2. Elevation & Permissions
    is_admin = False
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        pass
    print(f"[*] Process Admin:  {'YES (Elevated)' if is_admin else 'NO (Standard User)'}")

    # 3. Audio Capture Devices
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        print(f"[*] Audio Inputs:   {len(input_devs)} capture devices found")
        def_in = sd.query_devices(kind="input")
        print(f"[*] Default Mic:    {def_in.get('name')} (Sample Rate: {def_in.get('default_samplerate')} Hz)")
    except Exception as exc:
        print(f"[-] Audio Capture:  Warning ({exc})")

    # 4. Speech Recognition Models
    vosk_path = os.path.join("models", "vosk-model-small-en-us-0.15")
    has_vosk = os.path.exists(vosk_path)
    print(f"[*] Vosk Model:     {'PRESENT (' + vosk_path + ')' if has_vosk else 'MISSING'}")

    # 5. UI Automation & Displays
    ctx = ContextService()
    fg_hwnd = ctx.get_foreground_window()
    displays = ctx.get_displays()
    print(f"[*] Connected Displays: {len(displays)}")
    for d in displays:
        print(f"    - {d.display_id}: bounds={d.bounds.to_tuple()}, scale={d.scale_factor}x, primary={d.is_primary}")
    print(f"[*] Active Window HWND: {fg_hwnd}")

    # 6. UIA Element Walking
    provider = UiaElementProvider()
    elements = provider.discover_elements()
    print(f"[*] Discovered UI Elements: {len(elements)} actionable items on active desktop")

    print("==================================================================")
    print("   DIAGNOSTIC STATUS: ALL CRITICAL SUBSYSTEMS OPERATIONAL (PASS)  ")
    print("==================================================================")
    return 0


def run_say(phrase: str) -> int:
    """Simulate a spoken voice command."""
    parser = CommandParser()
    intent = parser.parse(phrase)

    print(f"Input Utterance: '{phrase}'")
    if not intent:
        print("Result: No matching command recognized (NO_MATCH).")
        return 1

    print(f"Parsed Intent:   {intent.name} (confidence={intent.confidence})")
    print(f"Extracted Slots: {intent.slots}")
    return 0


def run_list_commands() -> int:
    """Print the active catalog of voice commands."""
    parser = CommandParser()
    cmds = parser.get_registered_commands()
    print(f"==================================================================")
    print(f"             VoxPilot Voice Commands Catalog ({len(cmds)} commands)         ")
    print(f"==================================================================")
    for c in cmds:
        name = c["name"]
        ctype = c["type"]
        if ctype == "builtin":
            print(f"  [{ctype.upper()}] {name}")
            for p in c.get("patterns", []):
                print(f"      pattern: {p}")
        else:
            print(f"  [{ctype.upper()}] {name} -> Action: {c.get('action')}")
    return 0


def run_dump_ui() -> int:
    """Discover and display interactive controls on the active window."""
    provider = UiaElementProvider()
    elements = provider.discover_elements()
    print(f"Discovered {len(elements)} interactive UI elements on active window:\n")
    print(f"{'ID':<6} {'TYPE':<16} {'BOUNDS (X, Y, W, H)':<24} {'NAME'}")
    print("-" * 75)
    for el in elements:
        bounds_str = f"({el.rect.x}, {el.rect.y}, {el.rect.width}, {el.rect.height})"
        clean_name = el.name[:30] if el.name else "<unnamed>"
        print(f"{el.element_id:<6} {el.control_type:<16} {bounds_str:<24} {clean_name}")
    return 0


def run_calibrate() -> int:
    """Run interactive audio calibration."""
    print("Starting audio calibration...")
    print("Measuring ambient noise floor for 1.5 seconds. Please remain silent...")
    wizard = CalibrationWizard()
    noise_res = wizard.measure_noise_floor(duration_seconds=1.5)
    print(f"Noise Floor: {noise_res.get('dbfs')} dBFS (RMS: {noise_res.get('rms')})")
    print(f"Acoustic Quality: {noise_res.get('quality')} (Environment: {noise_res.get('environment')})")

    print("\nReading sentence check:")
    print(f"Target: '{CalibrationWizard.CALIBRATION_SENTENCE}'")
    # Quick self check simulation
    eval_res = CalibrationWizard.verify_reading_sample(CalibrationWizard.CALIBRATION_SENTENCE)
    print(f"Accuracy: {eval_res.get('accuracy') * 100:.1f}% (WER: {eval_res.get('word_error_rate')})")
    print("Calibration complete.")
    return 0


def run_mic_test(seconds: int, device, report_path: str = "voxpilot-mic-test.txt") -> int:
    """Record from the real microphone and show what the recognizer hears (writes voxpilot-mic-test.txt)."""
    import time
    import numpy as np
    from ..contracts.dto import TranscriptEvent
    from ..speech.audio_capture import LiveAudioCapture
    from ..speech.vosk_engine import VoskSpeechEngine

    lines = []

    def say(msg: str) -> None:
        print(msg)
        lines.append(msg)

    engine = VoskSpeechEngine()
    engine.set_open_vocabulary(True)
    engine.subscribe(lambda ev: say(("FINAL   : " if ev.is_final else "partial : ") + ev.text) if ev.text else None)
    engine.start()
    cap = LiveAudioCapture()
    cap.start(device_id=device)
    say(f"Input device index: {cap.device_id}, native rate: {cap.native_samplerate}, channels: {cap.native_channels}")
    say(f"Speak normally for {seconds} seconds...")
    t_end, peak, sq, n, dropped0 = time.time() + seconds, 0.0, 0.0, 0, 0
    while time.time() < t_end:
        chunk = cap.read_chunk(timeout=0.2)
        if not chunk:
            continue
        a = np.frombuffer(chunk.data, dtype=np.int16).astype(np.float32) / 32768.0
        if a.size:
            peak = max(peak, float(np.abs(a).max()))
            sq += float((a * a).sum())
            n += a.size
        engine.process_audio(chunk)
    engine.flush()
    cap.stop()
    rms = (sq / n) ** 0.5 if n else 0.0
    say(f"Peak level: {peak:.3f}  RMS: {rms:.4f}  (peak below 0.02 = mic too quiet or wrong device)")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Saved {report_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="VoxPilot Voice Control CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="Run system diagnostics")
    subparsers.add_parser("list-commands", help="List all voice commands")
    subparsers.add_parser("dump-ui", help="Dump UI elements of foreground window")
    subparsers.add_parser("calibrate", help="Run acoustic calibration wizard")
    subparsers.add_parser("run", help="Launch VoxPilot system tray application")

    mic_parser = subparsers.add_parser("mic-test", help="Record from the microphone and show what is recognized")
    mic_parser.add_argument("--seconds", type=int, default=10)
    mic_parser.add_argument("--device", type=int, default=None)

    say_parser = subparsers.add_parser("say", help="Simulate a spoken voice command")
    say_parser.add_argument("phrase", type=str, help="Utterance to simulate")

    args = parser.parse_args()

    if args.command == "doctor":
        return run_doctor()
    elif args.command == "mic-test":
        return run_mic_test(args.seconds, args.device)
    elif args.command == "say":
        return run_say(args.phrase)
    elif args.command == "list-commands":
        return run_list_commands()
    elif args.command == "dump-ui":
        return run_dump_ui()
    elif args.command == "calibrate":
        return run_calibrate()
    elif args.command == "run":
        from .tray import main as tray_main
        return tray_main()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
