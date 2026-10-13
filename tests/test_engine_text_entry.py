"""Engine text-entry wiring tests (Linux-safe: stubs Win32 and heavy deps)."""
import sys, ctypes, types
from unittest.mock import MagicMock
import pytest

if not hasattr(ctypes, "windll"):
    ctypes.windll = MagicMock()
import importlib
for m in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "psutil", "vosk", "uiautomation", "comtypes", "faster_whisper"):
    try:
        importlib.import_module(m)
    except Exception:
        sys.modules[m] = MagicMock()

from voxpilot.contracts.dto import EngineMode, TranscriptEvent  # noqa: E402


@pytest.fixture
def engine():
    try:
        from voxpilot.engine import VoxPilotEngine
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"engine not importable here: {exc}")
    inj = MagicMock()
    inj.type_unicode.return_value = True
    e = VoxPilotEngine(speech_engine=MagicMock(), element_provider=MagicMock(),
                       overlay_service=MagicMock(), input_injector=inj)
    e.dictation_service.context_service = None
    return e, inj


def say(e, t):
    e._on_transcript(TranscriptEvent(text=t, is_final=True))


def test_dictation_is_default(engine):
    e, _ = engine
    assert e.mode == EngineMode.DICTATION


def test_dictation_formats_and_types(engine):
    e, inj = engine
    say(e, "hello world comma how are you question mark")
    inj.type_unicode.assert_called()
    assert inj.type_unicode.call_args[0][0].startswith("Hello world, how are you?")


def test_spelling_mode_phonetic_alfa(engine):
    e, inj = engine
    say(e, "spelling mode")
    assert e.mode == EngineMode.SPELLING
    say(e, "alfa bravo charlie")
    assert inj.type_unicode.call_args[0][0] == "abc"


def test_command_mode_ignores_plain_text(engine):
    e, inj = engine
    say(e, "command mode")
    say(e, "random words here")
    inj.type_unicode.assert_not_called()


def test_commands_win_in_dictation_mode(engine):
    e, inj = engine
    say(e, "go to sleep")
    assert e.mode == EngineMode.SLEEP
