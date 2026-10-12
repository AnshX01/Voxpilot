"""Adversarial Attack Suite - Round 3 (System Hardening & Stress).

Targeting:
1. ReDoS (Regular Expression Denial of Service) resilience on CommandParser.
2. Rapid asynchronous mode thrashing (COMMAND <-> DICTATION <-> SLEEP 500x).
3. Extreme virtual multi-monitor coordinates (negative coordinates, enormous bounding boxes).
4. Malformed and corrupted TranscriptEvent payloads (NaN confidence, negative timestamps, extreme lengths).
5. Dictation history burst exhaustion and circular queue stress (>1,000 bursts).
6. Multi-threaded race conditions during concurrent command parsing and overlay paint.
"""

import math
import threading
import time
from unittest.mock import MagicMock
import pytest

from voxpilot.commands import CommandParser
from voxpilot.contracts.dto import (
    CommandResult,
    CommandStatus,
    EngineMode,
    Intent,
    LabeledElement,
    ScreenRect,
    TranscriptEvent,
    TranscriptWord,
)
from voxpilot.dictation.dictation_service import DictationService
from voxpilot.engine import VoxPilotEngine
from voxpilot.overlay.overlay_service import OverlayService


def test_redos_pattern_injection():
    """Verify that CommandParser is immune to catastrophic backtracking / ReDoS payloads."""
    parser = CommandParser()

    redos_payloads = [
        "a" * 1000,
        "press " + "ctrl " * 100 + "t",
        "click " + "number " * 100 + "5",
        "show " + "numbers " * 100,
        "zoom into " + "9 " * 100,
        "uh " * 200 + "please show numbers",
        "snap " * 100 + "left",
        "press down " + "5 " * 100 + "times",
    ]

    for payload in redos_payloads:
        t0 = time.perf_counter()
        # Parse must return in < 50ms, never hanging or timing out
        intent = parser.parse(payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert elapsed_ms < 50.0, f"ReDoS vulnerability detected on payload: {payload[:30]}... ({elapsed_ms:.2f}ms)"


def test_rapid_mode_thrashing_stress():
    """Stress test rapid mode transitions (COMMAND -> DICTATION -> SLEEP) across 500 cycles."""
    engine = VoxPilotEngine(
        speech_engine=MagicMock(),
        command_parser=CommandParser(),
        element_provider=MagicMock(),
        overlay_service=MagicMock(),
        input_injector=MagicMock(),
    )

    modes = ["start dictation", "stop dictation", "go to sleep", "wake up"]
    for i in range(500):
        cmd = modes[i % len(modes)]
        res = engine.process_text_command(cmd)
        assert res.status == CommandStatus.SUCCESS

    # Verify engine remains responsive and coherent
    assert engine.mode in (EngineMode.COMMAND, EngineMode.DICTATION, EngineMode.SLEEP)


def test_extreme_and_negative_screen_coordinates():
    """Verify overlay canvas and element index handle virtual displays with negative coordinates."""
    overlay = OverlayService()

    extreme_elements = [
        LabeledElement(
            element_id=1,
            name="Negative Screen Item",
            control_type="Button",
            rect=ScreenRect(x=-1920, y=-1080, width=1920, height=1080),
            window_handle=1001,
        ),
        LabeledElement(
            element_id=2,
            name="Massive 8K Canvas Item",
            control_type="Pane",
            rect=ScreenRect(x=0, y=0, width=7680, height=4320),
            window_handle=1002,
        ),
        LabeledElement(
            element_id=3,
            name="Sub-pixel Miniscule Control",
            control_type="Thumb",
            rect=ScreenRect(x=500, y=500, width=1, height=1),
            window_handle=1003,
        ),
    ]

    overlay.show_numbers(extreme_elements)
    assert overlay.is_numbers_visible()
    overlay.hide_numbers()
    assert not overlay.is_numbers_visible()


def test_malformed_transcript_event_tolerance():
    """Verify engine and dictation services tolerate malformed transcript payloads without crashing."""
    mock_injector = MagicMock()
    dictation_service = DictationService(injector=mock_injector)
    dictation_service.set_active(True)

    malformed_events = [
        TranscriptEvent(text="", is_final=True, confidence=0.0),
        TranscriptEvent(text="   \t\n   ", is_final=True, confidence=1.0),
        TranscriptEvent(text="valid word", is_final=False, confidence=-1.0),
        TranscriptEvent(text="another test", is_final=True, confidence=999.0),
        TranscriptEvent(
            text="word with empty words list",
            is_final=True,
            words=[TranscriptWord(word="", start_time_ms=-50, end_time_ms=-10, confidence=float("nan"))],
        ),
    ]

    for evt in malformed_events:
        res = dictation_service.handle_burst(evt)
        assert isinstance(res, CommandResult)


def test_dictation_circular_history_stress():
    """Verify atomic dictation history under 1,500 consecutive bursts and undos."""
    mock_injector = MagicMock()
    dictation_service = DictationService(injector=mock_injector, max_history=100)
    dictation_service.set_active(True)

    # Inject 1,500 bursts
    for i in range(1500):
        evt = TranscriptEvent(text=f"burst sentence {i} period", is_final=True)
        res = dictation_service.handle_burst(evt)
        assert res.status == CommandStatus.SUCCESS

    # History capacity is capped at max_history (100)
    assert len(dictation_service._history) == 100

    # Execute 150 'scratch that' commands (100 undos, then empty gracefully)
    for _ in range(150):
        res = dictation_service.handle_burst(TranscriptEvent(text="scratch that", is_final=True))
        assert res.status in (CommandStatus.SUCCESS, CommandStatus.NO_MATCH)


def test_concurrent_threading_race_protection():
    """Verify thread safety when multiple worker threads dispatch commands concurrently."""
    mock_elem_provider = MagicMock()
    mock_elem_provider.get_element_by_id.return_value = LabeledElement(
        element_id=1,
        name="Target Button",
        control_type="Button",
        rect=ScreenRect(x=100, y=100, width=50, height=25),
        window_handle=0,
    )
    mock_overlay = MagicMock()
    mock_overlay.is_grid_visible.return_value = False

    engine = VoxPilotEngine(
        speech_engine=MagicMock(),
        command_parser=CommandParser(),
        element_provider=mock_elem_provider,
        overlay_service=mock_overlay,
        input_injector=MagicMock(),
    )

    exceptions = []

    def worker(worker_id: int):
        try:
            for j in range(50):
                cmd = f"click {worker_id * 10 + (j % 5) + 1}"
                res = engine.process_text_command(cmd)
                assert isinstance(res, CommandResult)
        except Exception as exc:
            exceptions.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert exceptions == [], f"Thread race exceptions caught: {exceptions}"
