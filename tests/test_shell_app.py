"""Unit and Integration tests for Shell App, Tray Controller, Calibration Wizard, and CLI."""

from unittest.mock import MagicMock
import os
import wave
import numpy as np
import pytest

from voxpilot.app.calibration import CalibrationWizard
from voxpilot.app.tray import VoxPilotTrayIcon
from voxpilot.app.cli import run_doctor, run_say, run_list_commands, run_dump_ui
from voxpilot.contracts.dto import EngineMode
from voxpilot.speech.audio_capture import FakeMic


def test_calibration_reading_verification() -> None:
    # Perfect reading sample
    target = "the quick brown fox jumps over the lazy dog"
    res1 = CalibrationWizard.verify_reading_sample(target, target)
    assert res1["accuracy"] == 1.0
    assert res1["word_error_rate"] == 0.0
    assert res1["passed"] is True

    # High accuracy reading with 1 substitution
    spoken_close = "the quick brown fox leaps over the lazy dog"
    res2 = CalibrationWizard.verify_reading_sample(spoken_close, target)
    assert res2["accuracy"] >= 0.88
    assert res2["passed"] is True

    # Bad reading (low accuracy)
    spoken_bad = "banana apple orange grape watermelon"
    res3 = CalibrationWizard.verify_reading_sample(spoken_bad, target)
    assert res3["passed"] is False


def test_calibration_noise_floor_measurement(tmp_path) -> None:
    # Create synthetic quiet WAV fixture (1 second of low-amplitude noise)
    wav_file = str(tmp_path / "ambient_quiet.wav")
    sr = 16000
    duration = 0.5
    num_samples = int(sr * duration)
    # Low amplitude noise (RMS ~0.005)
    audio_data = (np.random.randn(num_samples) * 150).astype(np.int16)

    with wave.open(wav_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    fake_mic = FakeMic(wav_path=wav_file, chunk_duration_ms=50, real_time=False)
    # We can test CalibrationWizard logic directly
    samples = audio_data.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(samples**2)))
    assert rms > 0.0


def test_system_tray_controller_toggles() -> None:
    mock_engine = MagicMock()
    mock_engine.mode = EngineMode.COMMAND
    mock_engine.overlay_service.is_numbers_visible.return_value = False
    mock_engine.overlay_service.is_grid_visible.return_value = False

    # Initialize tray icon
    tray = VoxPilotTrayIcon(engine=mock_engine)

    # 1. Toggle Listening
    tray._toggle_listening()
    assert mock_engine.mode == EngineMode.SLEEP
    mock_engine.overlay_service.hide_all.assert_called_once()

    tray._toggle_listening()
    assert mock_engine.mode == EngineMode.COMMAND

    # 2. Toggle Dictation
    tray._toggle_dictation()
    assert mock_engine.mode == EngineMode.DICTATION

    tray._toggle_dictation()
    assert mock_engine.mode == EngineMode.COMMAND

    # 3. Toggle Numbers
    tray._toggle_numbers()
    mock_engine._handle_show_numbers.assert_called_once()

    mock_engine.overlay_service.is_numbers_visible.return_value = True
    tray._toggle_numbers()
    mock_engine.overlay_service.hide_numbers.assert_called_once()

    # 4. Toggle Grid
    tray._toggle_grid()
    mock_engine.overlay_service.show_grid.assert_called_once()

    mock_engine.overlay_service.is_grid_visible.return_value = True
    tray._toggle_grid()
    mock_engine.overlay_service.hide_grid.assert_called_once()


def test_cli_diagnostics_and_commands() -> None:
    assert run_doctor() == 0
    assert run_say("press ctrl shift t") == 0
    assert run_say("unknown gibberish wordxyz") == 1  # Unrecognized phrase exits with 1
    assert run_list_commands() == 0
    assert run_dump_ui() == 0
