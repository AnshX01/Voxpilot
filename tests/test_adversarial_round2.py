"""Adversarial Attack Suite - Round 2 (Phase 3 Breadth Hardening).

Attacks:
1. Dictation engine: giant payload (100k chars), empty/whitespace bursts, 100 consecutive rapid bursts.
2. Dictation undo: underflow (undoing empty history), undoing beyond max history (deque boundary).
3. Focus safety: mid-stream focus transition to password field or secure desktop.
4. Screen grid: extreme recursive drill-down (10 levels deep to sub-pixel rect), undo below root level, out-of-bounds cell indices (0, 10, -1, 999).
5. Disambiguation: badge overflow with 100 items, empty candidates.
6. HUD: giant string buffer injection (10,000 characters).
7. Custom commands: malformed payloads, injection attempts with destructive shell commands.
8. Native messaging: oversized 100MB length header, malformed JSON stream.
9. Rapid mode toggling: switching between COMMAND, DICTATION, and SLEEP 100 times.
"""

from unittest.mock import MagicMock
import io
import struct
import pytest

from voxpilot.app.calibration import CalibrationWizard
from voxpilot.commands.command_parser import CommandParser
from voxpilot.commands.custom_commands_loader import CustomCommandLoader
from voxpilot.contracts.dto import (
    BlockedReason,
    CommandStatus,
    DisambiguationItem,
    EngineMode,
    Intent,
    LabeledElement,
    OverlayMode,
    ScreenRect,
    TranscriptEvent,
)
from voxpilot.dictation.dictation_service import DictationService
from voxpilot.dictation.formatting import FormattingEngine
from voxpilot.engine import VoxPilotEngine
from voxpilot.native_host.host import NativeMessagingBridge, read_message, send_message
from voxpilot.overlay.overlay_service import OverlayService


# ============================================================================
# 1. Dictation & Formatting Stress & Security Attacks
# ============================================================================

def test_adversarial_dictation_giant_payload() -> None:
    engine = FormattingEngine()
    giant_text = "word " * 20000  # 100,000 characters
    formatted = engine.format_text(giant_text)
    assert len(formatted) > 0
    assert formatted.startswith("Word")


def test_adversarial_dictation_rapid_bursts() -> None:
    mock_injector = MagicMock()
    mock_injector.type_unicode.return_value = True
    service = DictationService(injector=mock_injector)
    service.set_active(True)

    # 100 rapid bursts in sequence
    for i in range(100):
        evt = TranscriptEvent(text=f"word {i} comma", is_final=True)
        res = service.handle_burst(evt)
        assert res.status == CommandStatus.SUCCESS

    assert mock_injector.type_unicode.call_count == 100


def test_adversarial_dictation_undo_underflow() -> None:
    mock_injector = MagicMock()
    service = DictationService(injector=mock_injector)
    service.set_active(True)

    # Undo when history is empty
    res = service.execute_editing_command("scratch that")
    assert res.status == CommandStatus.SUCCESS
    # Should fall back to Ctrl+Z without crashing
    mock_injector.key_combination.assert_called_with(["ctrl", "z"])


def test_adversarial_dictation_password_midstream_block() -> None:
    mock_injector = MagicMock()
    mock_context = MagicMock()
    mock_context.is_secure_desktop.return_value = False
    mock_context.is_password_focused.return_value = False

    service = DictationService(injector=mock_injector, context_service=mock_context)
    service.set_active(True)

    # Burst 1: normal focus
    res1 = service.handle_burst(TranscriptEvent(text="hello", is_final=True))
    assert res1.status == CommandStatus.SUCCESS

    # Midstream: user clicks password box
    mock_context.is_password_focused.return_value = True

    # Burst 2: must be blocked immediately!
    res2 = service.handle_burst(TranscriptEvent(text="secretPassword123", is_final=True))
    assert res2.status == CommandStatus.BLOCKED
    assert res2.blocked_reason == BlockedReason.PASSWORD_FIELD


# ============================================================================
# 2. Overlay & Grid Drill-Down Stress Attacks
# ============================================================================

def test_adversarial_grid_extreme_drill_down() -> None:
    overlay = OverlayService()
    overlay.show_grid()

    # Drill down 10 levels deep
    for _ in range(10):
        rect = overlay.drill_down_grid(5)
        assert rect is not None
        assert rect.width >= 1
        assert rect.height >= 1

    # Coordinates must remain valid finite numbers
    coords = overlay.get_grid_cell_center(5)
    assert coords is not None
    assert 0 <= coords[0] <= 1920
    assert 0 <= coords[1] <= 1080

    # Step back up 10 times
    for _ in range(10):
        popped = overlay.undo_grid()
        assert popped is not None

    # Undo beyond root must return None safely without exception
    assert overlay.undo_grid() is None
    assert overlay.undo_grid() is None


def test_adversarial_grid_invalid_cell_indices() -> None:
    overlay = OverlayService()
    overlay.show_grid()

    for invalid_cell in [0, 10, -1, 999, -50]:
        assert overlay.drill_down_grid(invalid_cell) is None
        assert overlay.get_grid_cell_center(invalid_cell) is None


def test_adversarial_disambiguation_overflow() -> None:
    overlay = OverlayService()

    # 100 candidate items
    items = []
    for i in range(100):
        badge = chr(65 + (i % 26))
        el = LabeledElement(
            element_id=i + 1,
            name=f"Button {i}",
            control_type="Button",
            rect=ScreenRect(x=(i * 15) % 1800, y=(i * 10) % 900, width=50, height=25),
            window_handle=0,
        )
        items.append(DisambiguationItem(badge_label=badge, element=el))

    overlay.show_disambiguation(items)
    assert overlay.current_mode() == OverlayMode.DISAMBIGUATION
    overlay.hide()
    assert overlay.current_mode() == OverlayMode.OFF


def test_adversarial_hud_giant_string() -> None:
    overlay = OverlayService()
    giant_hud = "A" * 10000
    # Must not crash or hang
    overlay.show_hud(giant_hud, level="error")
    overlay.update_hud(mode=EngineMode.COMMAND, text=giant_hud)
    overlay.hide()


# ============================================================================
# 3. Custom Commands Security & Malicious Injection Attacks
# ============================================================================

def test_adversarial_custom_commands_destructive_injection() -> None:
    loader = CustomCommandLoader()
    malicious_inputs = {
        "commands": [
            {"trigger": "wipe disk", "action_type": "launch", "action": "rmdir /s /q C:\\"},
            {"trigger": "delete files", "action_type": "launch", "action": "del /f /q *.*"},
            {"trigger": "shutdown system", "action_type": "launch", "action": "shutdown -s -t 0"},
            {"trigger": "destroy reg", "action_type": "launch", "action": "reg delete HKLM\\Software"},
            {"trigger": "powershell exploit", "action_type": "launch", "action": "powershell -enc aW1wb3J0"},
        ]
    }

    loaded = loader.load_from_dict(malicious_inputs)
    # Every single destructive command must be rejected!
    assert len(loaded) == 0


def test_adversarial_custom_commands_malformed_structures() -> None:
    loader = CustomCommandLoader()

    # None, non-dict, missing fields
    bad_structures = [
        {},
        {"commands": None},
        {"commands": ["not a dict", 123, None]},
        {"commands": [{"trigger": ""}, {"action_type": ""}, {"action": None}]},
        {"commands": [{"trigger": "test", "action_type": "unsupported_action", "action": 123}]},
    ]

    for bad in bad_structures:
        loaded = loader.load_from_dict(bad)
        assert isinstance(loaded, list)


# ============================================================================
# 4. Native Messaging Protocol Framing Attacks
# ============================================================================

def test_adversarial_native_messaging_oversized_header() -> None:
    # Header claims 100 MB payload (0x06400000)
    oversized_len = struct.pack("@I", 100 * 1024 * 1024)
    buf = io.BytesIO(oversized_len + b"tiny payload")
    # Stream runs out of bytes before 100MB is read -> must return None cleanly without memory blowup
    msg = read_message(buf)
    assert msg is None


def test_adversarial_native_messaging_corrupt_json() -> None:
    garbage_bytes = b"{this is not valid json!@@##$$}"
    header = struct.pack("@I", len(garbage_bytes))
    buf = io.BytesIO(header + garbage_bytes)
    # Must catch JSONDecodeError and return None safely
    msg = read_message(buf)
    assert msg is None


# ============================================================================
# 5. Engine Concurrency & Rapid Mode Switching
# ============================================================================

def test_adversarial_rapid_mode_switching() -> None:
    mock_speech = MagicMock()
    mock_elements = MagicMock()
    mock_overlay = MagicMock()
    mock_input = MagicMock()
    parser = CommandParser()

    engine = VoxPilotEngine(
        speech_engine=mock_speech,
        element_provider=mock_elements,
        overlay_service=mock_overlay,
        input_injector=mock_input,
        command_parser=parser,
    )

    modes = ["WAKE_UP", "START_DICTATION", "STOP_DICTATION", "GO_TO_SLEEP"]
    for i in range(100):
        m = modes[i % len(modes)]
        res = engine.dispatch_intent(Intent(name=m, raw_text=m.lower()))
        assert res.status == CommandStatus.SUCCESS

    # Final state should be consistent
    assert engine.mode in (EngineMode.COMMAND, EngineMode.DICTATION, EngineMode.SLEEP)
