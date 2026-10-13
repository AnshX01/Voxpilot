"""
End-to-End Vertical Slice Integration Test for Gate 2
Tests: Audio (FakeMic) -> Vosk STT -> Command-NLU -> UIA Discovery -> Overlay Badges -> Dynamic Grammar -> Number Click -> SendInput
"""

import time
import pytest
from voxpilot.engine import VoxPilotEngine
from voxpilot.speech import FakeMic
from voxpilot.contracts.dto import CommandStatus

def test_vertical_slice_fakemic_e2e():
    """Verify complete vertical slice using real audio fixtures played via FakeMic."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Step 1: Feed 'show numbers' audio fixture via FakeMic
        t0 = time.perf_counter()
        mic = FakeMic("fixtures/audio/show_numbers.wav", chunk_duration_ms=50, real_time=False)
        mic.start()

        while True:
            chunk = mic.read_chunk(timeout=0.05)
            if not chunk:
                break
            engine.speech_engine.process_audio(chunk)

        # Measure latency from end of utterance (post-speech endpoint)
        t_eos = time.perf_counter()
        engine.speech_engine.flush()
        t1 = time.perf_counter()

        post_speech_latency_ms = (t1 - t_eos) * 1000
        total_time_ms = (t1 - t0) * 1000

        print(f"\n[E2E] 'show numbers' post-utterance latency: {post_speech_latency_ms:.2f} ms (Total: {total_time_ms:.2f} ms)")

        # Verify overlay is visible and elements are discovered
        assert engine.overlay_service.is_numbers_visible() is True
        cached_elements = engine.element_provider.get_all_cached_elements()
        print(f"[E2E] Discovered & labeled {len(cached_elements)} elements")
        assert len(cached_elements) > 0

        # Budget assertion: Say "show numbers" -> labels visible <= 500 ms after end of utterance
        assert post_speech_latency_ms <= 500.0

        # Step 2: Feed 'twelve' click number audio fixture via FakeMic
        t2 = time.perf_counter()
        mic2 = FakeMic("fixtures/audio/twelve.wav", chunk_duration_ms=50, real_time=False)
        mic2.start()

        while True:
            chunk = mic2.read_chunk(timeout=0.05)
            if not chunk:
                break
            engine.speech_engine.process_audio(chunk)

        t_eos2 = time.perf_counter()
        engine.speech_engine.flush()
        t3 = time.perf_counter()

        post_click_latency_ms = (t3 - t_eos2) * 1000
        total_click_ms = (t3 - t2) * 1000

        print(f"[E2E] 'twelve' click post-utterance latency: {post_click_latency_ms:.2f} ms (Total: {total_click_ms:.2f} ms)")

        # Verify last result was CLICK_NUMBER
        assert engine._last_result is not None
        assert engine._last_result.matched_intent is not None
        assert engine._last_result.matched_intent.name == "CLICK_NUMBER"
        assert engine._last_result.matched_intent.slots.get("number") == 12

        # Budget assertion: Say a number -> target clicked <= 400 ms after end of utterance
        assert post_click_latency_ms <= 400.0

        # Element 12 click status
        if len(cached_elements) >= 12:
            assert engine._last_result.status == CommandStatus.SUCCESS
        else:
            assert engine._last_result.status == CommandStatus.ELEMENT_GONE

    finally:
        engine.stop()

def test_direct_say_e2e():
    """Verify programmatic 'say' interface across show numbers and clicks."""
    engine = VoxPilotEngine()
    engine.start()

    try:
        # Show numbers
        res1 = engine.process_text_command("show numbers")
        assert res1.is_success is True
        assert engine.overlay_service.is_numbers_visible() is True

        elements = engine.element_provider.get_all_cached_elements()
        assert len(elements) > 0

        # Click #1
        res2 = engine.process_text_command("1")
        assert res2.is_success is True
        assert res2.matched_intent.slots["number"] == 1
        assert engine.overlay_service.is_numbers_visible() is True  # stays until "hide numbers"

        # Hide numbers
        res3 = engine.process_text_command("hide numbers")
        assert res3.is_success is True
        assert engine.overlay_service.is_numbers_visible() is False

        # Show grid
        res4 = engine.process_text_command("show grid")
        assert res4.is_success is True
        assert engine.overlay_service.is_grid_visible() is True

        # Hide grid
        res5 = engine.process_text_command("hide grid")
        assert res5.is_success is True
        assert engine.overlay_service.is_grid_visible() is False

    finally:
        engine.stop()
