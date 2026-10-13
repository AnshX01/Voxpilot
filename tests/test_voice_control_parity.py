"""Apple Voice Control guide parity tests (grid model, phonetic editing, engine semantics)."""
import sys, ctypes, importlib
from unittest.mock import MagicMock
import pytest

if not hasattr(ctypes, "windll"):
    ctypes.windll = MagicMock()
for m in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "psutil", "vosk", "uiautomation", "comtypes", "faster_whisper"):
    try:
        importlib.import_module(m)
    except Exception:
        sys.modules[m] = MagicMock()

from voxpilot.overlay.grid_model import GridModel, Rect  # noqa: E402
from voxpilot.dictation.formatting import FormattingEngine  # noqa: E402
from voxpilot.contracts.dto import EngineMode, TranscriptEvent  # noqa: E402


def test_grid_top_level_is_7x4_numbered_row_major():
    g = GridModel(Rect(0, 0, 1144, 746))
    assert (g.cols, g.rows, g.count) == (7, 4, 28)
    assert g.cell_rect(1).x == 0 and g.cell_rect(8).y > 0 and g.cell_rect(28) is not None
    assert g.cell_rect(29) is None
    cx, cy = g.center(1)
    assert 0 < cx < 163 and 0 < cy < 187


def test_grid_drill_is_5x5_and_undo():
    g = GridModel(Rect(0, 0, 1920, 1080))
    assert g.drill(10)
    assert (g.cols, g.rows, g.count) == (5, 5, 25)
    b = g.bounds
    assert b.x >= 0 and b.y >= 0 and b.x + b.w <= 1920 and b.y + b.h <= 1080
    assert g.undo() and g.count == 28
    assert not g.undo()


def test_grid_eventually_cannot_drill_and_unframes():
    g = GridModel(Rect(0, 0, 1920, 1080))
    depth = 0
    while g.can_drill(13) and depth < 20:
        assert g.drill(13)
        depth += 1
    assert 1 <= depth < 20
    assert not g.drill(13)
    assert not g.framed()


def test_phonetic_replace_in_spelling_mode():
    f = FormattingEngine()
    assert f.phonetic_command("Replace Charlie Alfa Tango with Delta Oscar Golf") == "replace cat with dog"
    assert f.phonetic_command("replace cat with dog") == "replace cat with dog"


@pytest.fixture
def engine():
    try:
        from voxpilot.engine import VoxPilotEngine
    except Exception as exc:
        pytest.skip(f"engine not importable: {exc}")
    inj = MagicMock()
    ov = MagicMock()
    ov.is_grid_visible.return_value = True
    ov.grid_cell_count.return_value = 28
    ov.get_grid_cell_center.return_value = (100, 200)
    e = VoxPilotEngine(speech_engine=MagicMock(), element_provider=MagicMock(), overlay_service=ov, input_injector=inj)
    return e, inj, ov


def say(e, t):
    e._on_transcript(TranscriptEvent(text=t, is_final=True))


def test_bare_grid_number_drills_when_possible(engine):
    e, inj, ov = engine
    ov.can_drill_grid.return_value = True
    say(e, "command mode")
    say(e, "twelve")
    ov.drill_down_grid.assert_called_with(12)
    inj.click_at.assert_not_called()


def test_bare_grid_number_clicks_when_cannot_drill_and_grid_hides(engine):
    e, inj, ov = engine
    ov.can_drill_grid.return_value = False
    say(e, "command mode")
    say(e, "twelve")
    inj.click_at.assert_called()
    ov.hide_grid.assert_called()


def test_click_with_grid_number_clicks_and_grid_disappears(engine):
    e, inj, ov = engine
    ov.can_drill_grid.return_value = True
    say(e, "command mode")
    say(e, "click twelve")
    inj.click_at.assert_called()
    ov.hide_grid.assert_called()
    ov.drill_down_grid.assert_not_called()


def test_show_commands_context_lists_text_commands_first(engine):
    e, _, _ = engine
    say(e, "show commands")
    assert e.visible_commands[0][0] == "Text editing"
    say(e, "command mode")
    say(e, "show commands")
    assert e.visible_commands[0][0] == "Basic Navigation"


def test_recognizer_is_open_vocabulary_in_every_mode(engine):
    """Live bug: a closed command grammar turned ordinary speech into [unk]. Never constrain it."""
    e, _, _ = engine
    se = e.speech_engine
    for phrase in ("command mode", "dictation mode"):
        say(e, phrase)
        se.set_open_vocabulary.assert_called_with(True)


def test_vosk_engine_defaults_to_open_vocabulary(monkeypatch, tmp_path) -> None:
    from voxpilot.speech import vosk_engine as V

    calls = []
    monkeypatch.setattr(V.vosk, "Model", lambda path: object())

    class Rec:
        def __init__(self, *args):
            calls.append(args)

        def SetWords(self, _):
            pass

    monkeypatch.setattr(V.vosk, "KaldiRecognizer", Rec)
    eng = V.VoskSpeechEngine(model_path=str(tmp_path))
    eng.start()
    eng.set_grammar(["click ok"])
    assert all(len(c) == 2 for c in calls), "recognizer must not receive a closed grammar"


def test_tray_microphone_choice_restarts_capture(monkeypatch) -> None:
    from unittest.mock import MagicMock
    from voxpilot.app import tray as T

    monkeypatch.setattr(T.VoxPilotTrayIcon, "list_input_devices", staticmethod(lambda: [(1, "Mic A"), (3, "Mic B")]))
    eng = MagicMock()
    icon = T.VoxPilotTrayIcon(eng)
    icon.refresh_microphones()
    assert [a.text() for a in icon._mic_actions] == ["Mic A", "Mic B"]
    icon._select_microphone(3)
    eng.stop_live_capture.assert_called_once()
    eng.start_live_capture.assert_called_once_with(device_id=3)
    icon.refresh_microphones()
    assert [a.isChecked() for a in icon._mic_actions] == [False, True]


def test_numbers_refresh_follows_the_screen(engine) -> None:
    """Numbers must update when the screen changes, not stay a one-shot snapshot."""
    e, _, _ = engine
    e.is_running = True
    from voxpilot.contracts.dto import LabeledElement, ScreenRect

    def el(i, x):
        return LabeledElement(element_id=i, name=f"B{i}", control_type="Button",
                              rect=ScreenRect(x=x, y=10, width=40, height=20), window_handle=1)

    e.overlay_service = type("O", (), {})()
    shown = []
    e.overlay_service.is_numbers_visible = lambda: True
    e.overlay_service.is_continuous_numbers = lambda: False
    e.overlay_service.show_numbers = lambda els, continuous=False: shown.append([x.rect.x for x in els])
    e.element_provider.discover_elements = lambda *a, **k: [el(1, 5)]
    e._refresh_numbers()
    e._refresh_numbers()  # unchanged screen: no redraw
    e.element_provider.discover_elements = lambda *a, **k: [el(1, 99)]
    e._refresh_numbers()
    assert shown == [[5], [99]]


def test_final_transcripts_are_handled_off_the_audio_thread(engine) -> None:
    """A slow command must not block the thread feeding audio (continuous listening)."""
    import threading, time
    from voxpilot.contracts.dto import TranscriptEvent
    e, _, _ = engine
    e.is_running = True
    seen = []
    gate = threading.Event()

    def slow(ev):
        gate.wait(2)
        seen.append((ev.text, threading.current_thread().name))

    e._handle_final_event = slow
    e._start_dispatch_worker()
    t0 = time.perf_counter()
    e._on_transcript(TranscriptEvent(text="hello world", is_final=True))
    assert time.perf_counter() - t0 < 0.5  # returned immediately while handler is blocked
    gate.set()
    for _ in range(40):
        if seen:
            break
        time.sleep(0.05)
    assert seen and seen[0][1] == "voxpilot-dispatch"
    e.stop()


def test_overlay_calls_from_worker_thread_run_on_gui_thread() -> None:
    """Overlay mutations made off the GUI thread are queued to it (Qt widgets are not thread-safe)."""
    import threading
    from PySide6 import QtCore, QtWidgets
    from voxpilot.overlay.overlay_service import OverlayService
    ov = OverlayService()
    ov.gui_loop_running = True
    gui = threading.get_ident()
    ran = []
    orig = ov._canvas.hide
    ov._canvas.hide = lambda: (ran.append(threading.get_ident()), orig())[1]
    t = threading.Thread(target=ov.hide_all)
    t.start()
    app = QtWidgets.QApplication.instance()
    import time
    t0 = time.time()
    while t.is_alive() and time.time() - t0 < 3:
        app.processEvents()
        time.sleep(0.01)
    t.join()
    assert ran == [gui]


def test_stalled_gui_thread_never_runs_call_inline_or_late() -> None:
    """Loop flagged running but not serviced: the call is dropped, not run on the worker thread,
    and does not run later when the GUI thread finally processes events."""
    import threading
    from PySide6 import QtWidgets
    from voxpilot.overlay import overlay_service as osv
    ov = osv.OverlayService()
    ov.gui_loop_running = True
    ran = []
    orig = ov._canvas.hide
    ov._canvas.hide = lambda: (ran.append(threading.get_ident()), orig())[1]
    t = threading.Thread(target=ov.hide_all)
    t.start()
    t.join(8)  # GUI thread (this one) never services the queue during the wait
    assert not t.is_alive()
    assert ran == []                      # not executed inline on the worker
    QtWidgets.QApplication.instance().processEvents()
    assert ran == []                      # and not executed late (cancelled)


def test_stop_drops_queued_and_cleans_after_inflight(engine) -> None:
    import threading, time
    from voxpilot.contracts.dto import TranscriptEvent
    e, _, _ = engine
    e.is_running = True
    started, release, handled = threading.Event(), threading.Event(), []
    cleaned = []

    def handler(ev):
        started.set()
        release.wait(3)
        handled.append(ev.text)

    e._handle_final_event = handler
    e.overlay_service = type("O", (), {"hide_all": lambda s: cleaned.append("hide"),
                                       "stop_refresh": lambda s: None})()
    e.input_injector.release_all_modifiers = lambda: cleaned.append("mods")
    e._start_dispatch_worker()
    e._on_transcript(TranscriptEvent(text="one", is_final=True))
    started.wait(2)
    e._on_transcript(TranscriptEvent(text="two", is_final=True))  # queued behind the in-flight one
    e.stop()
    release.set()
    for _ in range(60):
        if "hide" in cleaned[2:] or cleaned.count("hide") >= 2:
            break
        time.sleep(0.05)
    assert handled == ["one"]             # queued utterance never ran after stop
    assert cleaned.count("hide") >= 2     # stop() cleanup plus post-in-flight cleanup


def test_mic_test_command_reports_levels(tmp_path, monkeypatch, capsys) -> None:
    """`mic-test` runs end to end against a fake capture device and writes its report."""
    import numpy as np
    from voxpilot.app import cli
    from voxpilot.contracts.dto import AudioChunk
    import voxpilot.speech.audio_capture as ac

    class FakeCap:
        device_id, native_samplerate, native_channels = 3, 48000, 1
        def __init__(self): self.n = 0
        def start(self, device_id=None): pass
        def stop(self): pass
        def read_chunk(self, timeout=0.2):
            self.n += 1
            t = np.arange(800) / 16000.0
            pcm = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
            return AudioChunk(data=pcm.tobytes())

    monkeypatch.setattr(ac, "LiveAudioCapture", FakeCap)
    assert cli.run_mic_test(1, None, str(tmp_path / "voxpilot-mic-test.txt")) == 0
    out = capsys.readouterr().out
    assert "Peak level: 0.3" in out
    assert (tmp_path / "voxpilot-mic-test.txt").exists()


def test_show_commands_opens_real_palette_and_hide_closes_it() -> None:
    from PySide6 import QtWidgets
    from voxpilot.overlay.overlay_service import OverlayService
    from voxpilot.app.command_catalog import commands_for_context
    ov = OverlayService()
    ov.show_commands_window(commands_for_context("general"))
    win = ov._commands_window
    assert win.isVisible() and win.windowTitle() == "Commands"
    assert win.tree.topLevelItem(0).text(0) == "Basic Navigation"
    assert win.tree.topLevelItem(0).child(0).text(0).startswith("Open")
    ov.hide_commands_window()
    QtWidgets.QApplication.instance().processEvents()
    assert not win.isVisible()


def test_open_voice_control_tutorial_command() -> None:
    from voxpilot.commands.command_parser import CommandParser
    intent = CommandParser().parse("open voice control tutorial")
    assert intent.name == "OPEN_TUTORIAL"
    assert CommandParser().parse("open mail").name != "OPEN_TUTORIAL"


def test_guide_basic_navigation_windows_equivalents_parse() -> None:
    from voxpilot.commands.command_parser import CommandParser
    p = CommandParser()
    expect = {"open document": "OPEN_DOCUMENT", "save document": "SAVE_DOCUMENT", "new item": "NEW_ITEM",
              "next app": "NEXT_APP", "previous app": "PREVIOUS_APP", "quit application": "QUIT_APP",
              "hide application": "HIDE_APP", "show keyboard": "SHOW_KEYBOARD",
              "hide keyboard": "HIDE_KEYBOARD", "repeat 3 times": "REPEAT_COMMAND"}
    for phrase, name in expect.items():
        assert p.parse(phrase).name == name, phrase
    assert p.parse("open mail").name == "OPEN_APP"


def test_repeat_runs_previous_command_n_times(engine) -> None:
    e, _, _ = engine
    e.is_running = True
    keys = []
    e.input_injector.key_combination = lambda k: keys.append(tuple(k)) or True
    assert e.process_text_command("save document").is_success
    assert e.process_text_command("repeat 3 times").is_success
    assert keys == [("ctrl", "s")] * 4
    assert e.process_text_command("hide application").is_success


def test_character_list_in_commands_rows() -> None:
    from voxpilot.app.command_catalog import commands_for_context
    rows = [r for r in commands_for_context("general") if r[0] == "Dictation and Spelling characters"]
    texts = [r[1] for r in rows]
    assert any(t.startswith("question mark") and "?" in t for t in texts)
    assert any(t.startswith("alpha") and t.endswith("a") for t in texts)
