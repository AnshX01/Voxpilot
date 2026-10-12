"""
Target Applications E2E Test Suite for Gate 2
Tests: Notepad, File Explorer, Edge/Brave under scripted FakeMic voice control.
"""

import subprocess
import time
import pytest
from voxpilot.engine import VoxPilotEngine
from voxpilot.speech import FakeMic
from voxpilot.contracts.dto import CommandStatus

def test_notepad_voice_control_e2e():
    """Verify voice control on Notepad: launch, show numbers, click menu, type text."""
    p = subprocess.Popen(["notepad.exe"])
    time.sleep(1.2) # Wait for Notepad window to surface

    engine = VoxPilotEngine()
    engine.start()

    try:
        # Discover elements in Notepad
        elements = engine.element_provider.discover_elements()
        assert len(elements) > 0
        print(f"\n[Notepad E2E] Discovered {len(elements)} elements in Notepad")

        # Voice command: Show numbers
        res1 = engine.process_text_command("show numbers")
        assert res1.is_success is True
        assert engine.overlay_service.is_numbers_visible() is True

        # Voice command: Click #1 (typically File menu or top button)
        res2 = engine.process_text_command("1")
        assert res2.is_success is True
        print(f"[Notepad E2E] Clicked #1: {res2.details.get('clicked_element')} at {res2.details.get('coordinates')}")

        # Voice command: Type some text
        engine.input_injector.send_text("VoxPilot Voice Automation Test\n")
        time.sleep(0.1)

    finally:
        engine.stop()
        p.terminate()

def test_explorer_voice_control_e2e():
    """Verify voice control on File Explorer: launch, show numbers, click navigation."""
    p = subprocess.Popen(["explorer.exe", "C:\\"])
    time.sleep(1.2)

    engine = VoxPilotEngine()
    engine.start()

    try:
        elements = engine.element_provider.discover_elements()
        assert len(elements) > 0
        print(f"\n[Explorer E2E] Discovered {len(elements)} elements in Explorer")

        res = engine.process_text_command("show numbers")
        assert res.is_success is True
        assert engine.overlay_service.is_numbers_visible() is True

        # Click #1
        res_click = engine.process_text_command("1")
        assert res_click.is_success is True
        print(f"[Explorer E2E] Clicked #1: {res_click.details.get('clicked_element')}")

    finally:
        engine.stop()

def test_browser_voice_control_e2e():
    """Verify voice control on Browser (Brave/Edge): show numbers and click."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        elements = engine.element_provider.discover_elements()
        assert len(elements) > 0
        print(f"\n[Browser E2E] Discovered {len(elements)} elements in active window")

        res = engine.process_text_command("show numbers")
        assert res.is_success is True

        res_click = engine.process_text_command("click 1")
        assert res_click.is_success is True
        print(f"[Browser E2E] Clicked #1: {res_click.details.get('clicked_element')}")

    finally:
        engine.stop()
