"""
Adversarial Test Suite - Round 1 (Phase 2 Core Vertical Slice)
Owned by: Adversary Subagent
Tests attacks against:
- Rapid fire command bursts ("show numbers", "hide numbers", "show numbers", "1", "999", "banana")
- Out-of-bounds number requests (element #999 when only 50 exist, negative numbers, 0, 1000+)
- Element lookup and click injection on destroyed / closed windows
- Sudden engine stop and modifier key recovery (stuck keys attack)
- Corrupt, odd-byte, high-amplitude, and silent audio fed into speech engine
- Malformed intent inputs, missing slots, type corruption
- Sleep mode command containment
- Whisper speech engine contract compliance
- Custom command regex injection and ReDoS vulnerabilities
- Overlay badge limit thresholds (elements >= 300)
"""

import os
import time
import ctypes
from unittest.mock import patch
import pytest
from typing import List

from voxpilot.engine import VoxPilotEngine
from voxpilot.speech import VoskSpeechEngine, FakeMic
from voxpilot.speech.whisper_engine import WhisperSpeechEngine
from voxpilot.commands import CommandParser, NumberParser
from voxpilot.input import WindowsInputInjector
from voxpilot.contracts.dto import (
    AudioChunk,
    Intent,
    EngineMode,
    MouseButton,
    CommandStatus,
    LabeledElement,
    ScreenRect,
    ActionType,
)
from voxpilot.contracts.errors import InputInjectionError

user32 = ctypes.windll.user32


# ============================================================================
# Attack Vector 1: Rapid Fire Command Bursts
# ============================================================================

def test_adversarial_rapid_fire_burst():
    """Attack: Rapid burst of commands alternating between show, hide, numbers, and garbage.
    
    Sequence: ["show numbers", "hide numbers", "show numbers", "1", "999", "banana"].
    Verify system maintains consistent state without crashing or deadlock.
    """
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Step 1: "show numbers" -> success, overlay becomes visible
        res0 = engine.process_text_command("show numbers")
        assert res0.status == CommandStatus.SUCCESS
        assert engine.overlay_service.is_numbers_visible() is True

        # Step 2: "hide numbers" -> success, overlay hidden
        res1 = engine.process_text_command("hide numbers")
        assert res1.status == CommandStatus.SUCCESS
        assert engine.overlay_service.is_numbers_visible() is False

        # Step 3: "show numbers" -> success, overlay visible again
        res2 = engine.process_text_command("show numbers")
        assert res2.status == CommandStatus.SUCCESS
        assert engine.overlay_service.is_numbers_visible() is True

        # Step 4: "1" -> success, clicks #1 and dismisses overlay
        res3 = engine.process_text_command("1")
        assert res3.status == CommandStatus.SUCCESS
        assert res3.matched_intent.slots["number"] == 1
        assert engine.overlay_service.is_numbers_visible() is False

        # Step 5: "999" -> element_gone (element does not exist)
        res4 = engine.process_text_command("999")
        assert res4.status == CommandStatus.ELEMENT_GONE
        assert res4.code == "ERR_ELEMENT_NOT_FOUND"

        # Step 6: "banana" -> no_match
        res5 = engine.process_text_command("banana")
        assert res5.status == CommandStatus.NO_MATCH
        assert res5.code == "ERR_NO_MATCH"

        # Verify engine history length
        assert len(engine._history) == 6

    finally:
        engine.stop()


def test_adversarial_rapid_fire_stress():
    """Attack: 50 back-to-back command calls in zero-delay succession."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        for i in range(25):
            res_show = engine.process_text_command("show numbers")
            assert res_show.is_success is True
            res_hide = engine.process_text_command("hide numbers")
            assert res_hide.is_success is True

        assert len(engine._history) == 50
        assert engine.overlay_service.is_numbers_visible() is False
    finally:
        engine.stop()


# ============================================================================
# Attack Vector 2: Out-Of-Bounds Number Requests
# ============================================================================

def test_adversarial_out_of_bounds_numbers():
    """Attack: Requesting element #999 when only ~50 exist, plus 0, negative, and 1000+."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Populate elements
        engine.process_text_command("show numbers")
        elements = engine.element_provider.get_all_cached_elements()
        num_elements = len(elements)
        assert num_elements > 0

        # Request element #999
        res_999 = engine.process_text_command("999")
        assert res_999.status == CommandStatus.ELEMENT_GONE
        assert res_999.code == "ERR_ELEMENT_NOT_FOUND"

        # Request element #1000 (NumberParser rejects > 999)
        res_1000 = engine.process_text_command("1000")
        assert res_1000.status == CommandStatus.NO_MATCH

        # Request element #0 ("0" is parsed as 0 by NumberParser, but rejected by CommandParser)
        res_0 = engine.process_text_command("0")
        assert res_0.status == CommandStatus.NO_MATCH

        # Request element ID num_elements + 10
        oob_id = num_elements + 10
        res_oob = engine.process_text_command(str(oob_id))
        assert res_oob.status == CommandStatus.ELEMENT_GONE
        assert res_oob.code == "ERR_ELEMENT_NOT_FOUND"

    finally:
        engine.stop()


# ============================================================================
# Attack Vector 3: Element Lookup On Destroyed / Closed Window
# ============================================================================

def test_adversarial_discover_on_destroyed_hwnd():
    """Attack: Pass an invalid/dead HWND directly to discover_elements."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Pass a bogus HWND (0xDEADBEEF)
        bogus_hwnd = 0xDEADBEEF
        elements = engine.element_provider.discover_elements(window_handle=bogus_hwnd)
        # Should gracefully return empty list, not crash
        assert elements == []
    finally:
        engine.stop()


def test_adversarial_click_on_destroyed_window():
    """Attack: Window was discovered, then closed/destroyed before click command arrived.
    
    Expected: Engine should verify window validity (`user32.IsWindow`) and return
    CommandStatus.ELEMENT_GONE, preventing accidental clicks on whatever is underneath.
    Actual: Engine blindly clicks at the stale coordinates and returns SUCCESS.
    """
    engine = VoxPilotEngine()
    engine.start()

    try:
        dead_hwnd = 0xBAADF00D
        assert not user32.IsWindow(dead_hwnd)

        fake_element = LabeledElement(
            element_id=1,
            name="OrphanedButton",
            control_type="Button",
            rect=ScreenRect(200, 200, 50, 30),
            window_handle=dead_hwnd,
            runtime_id="dead_1",
            stability_key="dead_key",
            is_password=False,
            supported_actions=[ActionType.CLICK],
        )
        engine.element_provider._cached_elements = [fake_element]

        res = engine.process_text_command("1")
        # System SHOULD detect that the target window has ceased to exist
        assert res.status == CommandStatus.ELEMENT_GONE
        assert res.code in ("ERR_ELEMENT_NOT_FOUND", "ERR_WINDOW_GONE")
    finally:
        engine.stop()


# ============================================================================
# Attack Vector 4: Sudden Engine Stop & Modifier Key Cleanup
# ============================================================================

def test_adversarial_release_all_modifiers():
    """Attack: Verify release_all_modifiers sends KEYUP events for all modifier keys."""
    injector = WindowsInputInjector()

    with patch("ctypes.windll.user32.SendInput") as mock_send_input:
        injector.release_all_modifiers()
        # Should send 5 SendInput calls (Shift, Ctrl, Alt, LWin, RWin)
        assert mock_send_input.call_count == 5


def test_adversarial_sudden_engine_stop():
    """Attack: Stop engine abruptly; verify overlay is hidden and modifiers cleaned."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Abrupt engine stop
        engine.stop()
        assert engine.is_running is False
        assert engine.overlay_service.is_numbers_visible() is False
    finally:
        engine.input_injector.release_all_modifiers()


def test_adversarial_stuck_modifiers_on_send_key_failure():
    """Attack: Call send_key with modifiers and an invalid key name.
    
    Expected: send_key cleans up held modifiers in a finally block even on error.
    Actual: Exception interrupts execution before key_up, leaving modifiers logically stuck.
    """
    injector = WindowsInputInjector()
    released_keys = []

    original_key_up = injector.key_up

    def tracking_key_up(key: str) -> None:
        released_keys.append(key)
        original_key_up(key)

    injector.key_up = tracking_key_up

    try:
        with pytest.raises(InputInjectionError):
            injector.send_key("NON_EXISTENT_KEY_XYZ", modifiers=["ctrl", "shift"])

        # Both modifiers SHOULD have been released in a finally block
        assert "shift" in released_keys
        assert "ctrl" in released_keys
    finally:
        injector.release_all_modifiers()


# ============================================================================
# Attack Vector 5: Corrupt, Odd-Byte, and Silent Audio in Speech Engine
# ============================================================================

def test_adversarial_speech_corrupt_and_silent_audio():
    """Attack: Feed empty, odd-byte, random noise, clipping, and 10s of silence into Vosk.
    
    Verify speech engine does not segfault, raise uncaught exceptions, or hang.
    """
    engine = VoskSpeechEngine()
    engine.start()

    try:
        # 1. Zero-length chunk
        engine.process_audio(AudioChunk(data=b"", sample_rate=16000, channels=1, timestamp_ms=0))

        # 2. Odd-length byte buffer (1 byte: invalid 16-bit PCM alignment)
        engine.process_audio(AudioChunk(data=b"\x00", sample_rate=16000, channels=1, timestamp_ms=10))

        # 3. Random byte noise (16KB)
        engine.process_audio(AudioChunk(data=os.urandom(16384), sample_rate=16000, channels=1, timestamp_ms=20))

        # 4. Maximum square-wave clipping (+32767 / -32768)
        clipping_pcm = (b"\x7f\xff\x80\x00" * 4000)
        engine.process_audio(AudioChunk(data=clipping_pcm, sample_rate=16000, channels=1, timestamp_ms=30))

        # 5. 10 seconds of pure digital silence (320,000 bytes)
        silence_chunk = AudioChunk(data=b"\x00" * 32000, sample_rate=16000, channels=1, timestamp_ms=40)
        for _ in range(10):
            engine.process_audio(silence_chunk)

        # 6. Flush at silence boundary
        engine.flush()

        metrics = engine.get_metrics()
        assert metrics["chunks_processed"] == 14
        assert metrics["engine"] == "vosk"

    finally:
        engine.stop()


def test_adversarial_dynamic_grammar_fuzzing():
    """Attack: set_grammar with emojis, newlines, tabs, quotes, backslashes, empty items."""
    engine = VoskSpeechEngine()
    engine.start()

    try:
        fuzzed_grammar = [
            'save & exit',
            '"quoted" string',
            'back\\slash',
            'new\nline',
            'emoji 😀 🎉',
            'null \x00 char',
            'tab\tseparated',
            '123 456',
            'supercalifragilisticexpialidocious',
            '',
            '    ',
        ]
        engine.set_grammar(fuzzed_grammar)

        # Process audio after fuzz grammar update
        chunk = AudioChunk(data=b"\x00" * 3200, sample_rate=16000, channels=1, timestamp_ms=0)
        engine.process_audio(chunk)
        engine.flush()
    finally:
        engine.stop()


# ============================================================================
# Attack Vector 6: Malformed Intent Inputs & Engine Resilience
# ============================================================================

def test_adversarial_malformed_intents_basic():
    """Attack: Dispatch intents with empty names, missing slots, string numbers, massive numbers."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        # 1. Empty intent name
        res1 = engine.dispatch_intent(Intent(name="", slots={}, raw_text=""))
        assert res1.status == CommandStatus.NO_MATCH

        # 2. Unknown intent
        res2 = engine.dispatch_intent(Intent(name="UNKNOWN_ACTION_XYZ", slots={}, raw_text="xyz"))
        assert res2.status == CommandStatus.NO_MATCH

        # 3. CLICK_NUMBER with missing slot
        res3 = engine.dispatch_intent(Intent(name="CLICK_NUMBER", slots={}, raw_text="click"))
        assert res3.status == CommandStatus.NO_MATCH

        # 4. CLICK_NUMBER with None slot
        res4 = engine.dispatch_intent(Intent(name="CLICK_NUMBER", slots={"number": None}, raw_text="click"))
        assert res4.status == CommandStatus.NO_MATCH

        # 5. CLICK_NUMBER with string slot ("banana")
        res5 = engine.dispatch_intent(Intent(name="CLICK_NUMBER", slots={"number": "banana"}, raw_text="click banana"))
        assert res5.status == CommandStatus.ELEMENT_GONE

        # 6. CLICK_NUMBER with huge number
        res6 = engine.dispatch_intent(Intent(name="CLICK_NUMBER", slots={"number": 999999999}, raw_text="click huge"))
        assert res6.status == CommandStatus.ELEMENT_GONE

    finally:
        engine.stop()


def test_adversarial_scroll_malformed_slots():
    """Attack: Dispatch SCROLL with invalid slot types (amount=None, amount='huge').
    
    Expected: Engine validates slot types and returns an error result.
    Actual: Uncaught TypeError crashes dispatch_intent.
    """
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Corrupt amount string
        res = engine.dispatch_intent(Intent(name="SCROLL", slots={"direction": "sideways", "amount": "huge"}))
        assert res.status in (CommandStatus.NO_MATCH, CommandStatus.ERROR)
    finally:
        engine.stop()


def test_adversarial_click_name_empty_string():
    """Attack: Dispatch CLICK_NAME with an empty string name while elements are cached.
    
    Expected: Engine returns ELEMENT_GONE or NO_MATCH.
    Actual: fuzzy_match_element checks `"" in name` (True), matching the first element and clicking it!
    """
    engine = VoxPilotEngine()
    engine.start()

    try:
        el = LabeledElement(
            1, "CriticalAction", "Button", ScreenRect(100, 100, 50, 50), 1, "1", "k1", False, [ActionType.CLICK]
        )
        engine.element_provider._cached_elements = [el]

        res = engine.dispatch_intent(Intent("CLICK_NAME", slots={"name": ""}, raw_text="click"))
        # Should NOT match CriticalAction
        assert res.status == CommandStatus.ELEMENT_GONE
        assert res.details.get("clicked_element") is None
    finally:
        engine.stop()


# ============================================================================
# Attack Vector 7: Dictation Engine (Whisper) Contract Compliance
# ============================================================================

def test_adversarial_whisper_engine_contract():
    """Attack: Ingest AudioChunk into WhisperSpeechEngine.
    
    Expected: Whisper ingests chunk.data bytes cleanly.
    Actual: Crashes with AttributeError: 'AudioChunk' object has no attribute 'pcm_bytes'.
    """
    engine = WhisperSpeechEngine()
    engine.start()

    try:
        chunk = AudioChunk(data=b"\x00" * 3200, sample_rate=16000, channels=1, timestamp_ms=0)
        # Should not raise AttributeError
        engine.process_audio(chunk)
    finally:
        engine.stop()


# ============================================================================
# Attack Vector 8: Sleep Mode Command Isolation
# ============================================================================

def test_adversarial_sleep_mode_isolation():
    """Attack: Issue active commands while engine is asleep.
    
    Expected: When in EngineMode.SLEEP, commands other than WAKE_UP should be ignored / blocked.
    Actual: process_text_command executes all commands unimpeded.
    """
    engine = VoxPilotEngine()
    engine.start()

    try:
        engine.process_text_command("go to sleep")
        assert engine.mode == EngineMode.SLEEP

        # Attempt to show grid while asleep
        res = engine.process_text_command("show grid")
        # Grid must not be displayed while asleep
        assert engine.overlay_service.is_grid_visible() is False
        assert res.status != CommandStatus.SUCCESS

    finally:
        engine.stop()


# ============================================================================
# Attack Vector 9: Custom Command Regex Injection
# ============================================================================

def test_adversarial_custom_command_regex_injection():
    """Attack: Register custom commands containing unescaped regex metacharacters or duplicate placeholders.
    
    Expected: Command parser sanitizes or safely escapes regex patterns.
    Actual: Unhandled PatternError crashes all subsequent parser calls.
    """
    cp = CommandParser()

    # Pattern with unescaped bracket
    cp.register_custom_command("open [file", "open_action")
    # Pattern with duplicate placeholder
    cp.register_custom_command("find <text> in <text>", "find_action")

    # Should not raise PatternError
    res = cp.parse("open test")
    assert res is not None or res is None


# ============================================================================
# Attack Vector 10: Overlay Badge Limit Thresholds (Element ID >= 300)
# ============================================================================

def test_adversarial_overlay_badge_cache_limit():
    """Attack: Provide element with ID >= 300 to show_numbers.
    
    Expected: Overlay service has badges rendered or dynamically generates them for 300-999.
    Actual: badge_cache only has keys "1".."299"; element 300+ has no badge rendered.
    """
    engine = VoxPilotEngine()
    engine.start()

    try:
        el_300 = LabeledElement(
            element_id=300,
            name="Button300",
            control_type="Button",
            rect=ScreenRect(100, 100, 50, 30),
            window_handle=1,
            runtime_id="300",
            stability_key="key300",
            is_password=False,
            supported_actions=[ActionType.CLICK],
        )

        engine.overlay_service.show_numbers([el_300])
        canvas = engine.overlay_service._canvas
        assert canvas is not None
        # Verify badge exists for 300
        assert "300" in canvas.badge_cache
    finally:
        engine.stop()
