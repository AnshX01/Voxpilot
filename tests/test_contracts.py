"""Unit tests for VoxPilot Core Contracts and DTOs."""

import sys
import time
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from voxpilot.contracts import (
    ActionType,
    AmbiguousCommandError,
    AudioChunk,
    AudioDeviceError,
    BlockedActionError,
    BlockedReason,
    CancellationError,
    CancellationToken,
    CommandResult,
    CommandStatus,
    ConfirmationRequest,
    ConfirmationRequiredError,
    DisambiguationItem,
    DisplayInfo,
    ElementGoneError,
    ElementNotFoundError,
    EngineMode,
    FocusState,
    GridTarget,
    IAudioCaptureService,
    ICommandDispatcher,
    ICommandParser,
    IContextService,
    IDictationService,
    IElementActionService,
    IElementProvider,
    IFeedbackService,
    IInputInjector,
    InputInjectionError,
    Intent,
    IOverlayService,
    ISpeechEngine,
    LabeledElement,
    MouseButton,
    OverlayMode,
    PasswordFieldBlockedError,
    RecognitionTimeoutError,
    ScreenRect,
    ScrollDirection,
    SecureDesktopBlockedError,
    TranscriptEvent,
    TranscriptWord,
    UIPIBlockedError,
    VoxPilotError,
)


# ============================================================================
# ScreenRect Tests
# ============================================================================


def test_screen_rect_properties():
    rect = ScreenRect(x=100, y=200, width=400, height=300)
    assert rect.left == 100
    assert rect.top == 200
    assert rect.right == 500
    assert rect.bottom == 500
    assert rect.center() == (300, 350)
    assert rect.area() == 120000
    assert not rect.is_empty()
    assert rect.to_tuple() == (100, 200, 400, 300)


def test_screen_rect_contains():
    rect = ScreenRect(x=50, y=50, width=100, height=100)
    assert rect.contains(50, 50)
    assert rect.contains(100, 100)
    assert rect.contains(149, 149)
    assert not rect.contains(49, 50)
    assert not rect.contains(150, 100)
    assert not rect.contains(100, 150)


def test_screen_rect_intersection():
    r1 = ScreenRect(x=0, y=0, width=100, height=100)
    r2 = ScreenRect(x=50, y=50, width=100, height=100)
    assert r1.intersects(r2)
    inter = r1.intersection(r2)
    assert inter is not None
    assert inter == ScreenRect(x=50, y=50, width=50, height=50)

    # Disjoint rectangles
    r3 = ScreenRect(x=200, y=200, width=50, height=50)
    assert not r1.intersects(r3)
    assert r1.intersection(r3) is None


def test_screen_rect_union():
    r1 = ScreenRect(x=10, y=20, width=30, height=40)
    r2 = ScreenRect(x=50, y=60, width=20, height=20)
    union_rect = r1.union(r2)
    assert union_rect == ScreenRect(x=10, y=20, width=60, height=60)


# ============================================================================
# Core DTO & Factory Tests
# ============================================================================


def test_labeled_element():
    rect = ScreenRect(x=10, y=10, width=100, height=30)
    elem = LabeledElement(
        element_id=42,
        name="Submit Button",
        control_type="Button",
        rect=rect,
        window_handle=123456,
        stability_key="sha256_mock_key",
        supported_actions=[
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.TRIPLE_CLICK,
            ActionType.LONG_PRESS,
            ActionType.DRAG,
            ActionType.FOCUS,
        ],
        is_focused=True,
        depth=3,
        z_index=10,
    )
    assert elem.element_id == 42
    assert elem.name == "Submit Button"
    assert elem.rect.center() == (60, 25)
    assert ActionType.CLICK in elem.supported_actions
    assert ActionType.TRIPLE_CLICK in elem.supported_actions
    assert ActionType.LONG_PRESS in elem.supported_actions
    assert ActionType.DRAG in elem.supported_actions
    assert not elem.is_password
    assert elem.is_focused is True
    assert elem.depth == 3
    assert elem.z_index == 10
    assert OverlayMode.CONTINUOUS_NUMBERS.value == "continuous_numbers"


def test_command_result_factories():
    # Success factory
    res_ok = CommandResult.success(message="Clicked #42", execution_time_ms=12.5)
    assert res_ok.is_success
    assert res_ok.status == CommandStatus.SUCCESS
    assert res_ok.code == "OK"
    assert res_ok.execution_time_ms == 12.5

    # No match factory
    res_nm = CommandResult.no_match(raw_text="foobar")
    assert not res_nm.is_success
    assert res_nm.status == CommandStatus.NO_MATCH
    assert res_nm.details["raw_text"] == "foobar"

    # Ambiguous factory
    res_amb = CommandResult.ambiguous(candidates=[1, 2, 3])
    assert res_amb.status == CommandStatus.AMBIGUOUS
    assert res_amb.details["candidates_count"] == 3

    # Element gone factory
    res_gone = CommandResult.element_gone(element_id=99)
    assert res_gone.status == CommandStatus.ELEMENT_GONE
    assert res_gone.details["element_id"] == 99

    # Blocked factory
    res_blk = CommandResult.blocked(
        reason=BlockedReason.UIPI, message="Admin window blocked"
    )
    assert res_blk.status == CommandStatus.BLOCKED
    assert res_blk.blocked_reason == BlockedReason.UIPI

    # Timeout factory
    res_to = CommandResult.timeout(message="UIA query timed out")
    assert res_to.status == CommandStatus.TIMEOUT

    # Error factory
    err = RuntimeError("Unexpected Win32 crash")
    res_err = CommandResult.error(err)
    assert res_err.status == CommandStatus.ERROR
    assert res_err.error_type == "RuntimeError"


def test_audio_chunk_num_samples_computation():
    # 3200 bytes of 16-bit mono PCM = 1600 samples
    raw_pcm = b"\x00" * 3200
    chunk = AudioChunk(data=raw_pcm, sample_rate=16000, channels=1)
    assert chunk.num_samples == 1600


def test_confirmation_request_expiry():
    intent = Intent(name="close_window", slots={})
    req = ConfirmationRequest(
        request_id="req-1",
        prompt_message="Close without saving?",
        command_intent=intent,
        timeout_seconds=0.05,
    )
    assert not req.is_expired()
    time.sleep(0.06)
    assert req.is_expired()


def test_cancellation_token():
    token = CancellationToken()
    assert not token.is_cancelled

    cleaned_up = False

    def on_cancel():
        nonlocal cleaned_up
        cleaned_up = True

    token.register_callback(on_cancel)
    token.cancel()
    assert token.is_cancelled
    assert cleaned_up

    with pytest.raises(CancellationError):
        token.throw_if_cancelled()


# ============================================================================
# Exception Hierarchy Tests
# ============================================================================


def test_exceptions_hierarchy():
    assert issubclass(UIPIBlockedError, BlockedActionError)
    assert issubclass(BlockedActionError, VoxPilotError)
    assert issubclass(ElementNotFoundError, VoxPilotError)
    assert issubclass(ElementGoneError, VoxPilotError)
    assert issubclass(InputInjectionError, VoxPilotError)
    assert issubclass(AudioDeviceError, VoxPilotError)
    assert issubclass(RecognitionTimeoutError, VoxPilotError)
    assert issubclass(SecureDesktopBlockedError, BlockedActionError)
    assert issubclass(PasswordFieldBlockedError, BlockedActionError)
    assert issubclass(ConfirmationRequiredError, BlockedActionError)

    err = UIPIBlockedError(hwnd=0x1234)
    assert err.hwnd == 0x1234
    assert err.code == "ERR_BLOCKED_UIPI"
    assert "Administrator" in str(err)


# ============================================================================
# Runtime Protocol Compliance Tests
# ============================================================================


class DummySpeechEngine:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_running(self) -> bool:
        return True

    def feed_audio(self, chunk: bytes) -> None:
        pass

    def set_grammar(self, words_or_phrases: list[str]) -> None:
        pass

    def set_mode(self, mode: EngineMode) -> None:
        pass

    def subscribe_transcripts(self, callback) -> None:
        pass

    def unsubscribe_transcripts(self, callback) -> None:
        pass

    def get_latency_metrics(self) -> dict[str, float]:
        return {"avg_rtf": 0.25}


class DummyOverlayService:
    def show_numbers(self, elements: list[LabeledElement]) -> None:
        pass

    def show_names(self, elements: list[LabeledElement]) -> None:
        pass

    def show_grid(self, display_id=None, sub_rect=None) -> None:
        pass

    def show_disambiguation(self, items, target_rect=None) -> None:
        pass

    def show_hud(self, message: str, duration_ms: int = 2000, level: str = "info") -> None:
        pass

    def hide(self) -> None:
        pass

    def is_visible(self) -> bool:
        return False

    def current_mode(self) -> OverlayMode:
        return OverlayMode.OFF


class DummyInputInjector:
    def mouse_move(self, x: int, y: int) -> bool:
        return True

    def mouse_click(self, x=None, y=None, button=MouseButton.LEFT, count=1) -> bool:
        return True

    def mouse_drag(self, start_x, start_y, end_x, end_y, duration_ms=200) -> bool:
        return True

    def mouse_scroll(self, delta_y: int, delta_x: int = 0) -> bool:
        return True

    def key_down(self, key: str) -> bool:
        return True

    def key_up(self, key: str) -> bool:
        return True

    def key_press(self, key: str) -> bool:
        return True

    def key_combination(self, keys: list[str]) -> bool:
        return True

    def type_unicode(self, text: str) -> bool:
        return True

    def release_all_modifiers(self) -> None:
        pass


class DummyElementProvider:
    def discover_elements(self, window_handle=None, screen_rect=None):
        return []

    def filter_visible_actionable(self, elements):
        return []

    def compute_stability_key(self, element):
        return "sha256"

    def activate_chromium_window(self, hwnd):
        return True

    def get_element_by_id(self, element_id):
        return None

    def get_element_by_stability_key(self, key):
        return None

    def invalidate_cache(self):
        pass


class DummyCommandParser:
    def parse(self, text, context=None):
        return None

    def parse_number(self, text_token):
        return 42

    def get_registered_patterns(self):
        return ["click <number>"]

    def register_dynamic_keywords(self, keywords):
        pass

    def match_element_label(self, spoken_label, candidates):
        return []


class DummyDictationService:
    def handle_burst(self, transcript):
        return CommandResult.success()

    def apply_formatting(self, raw_text, formatting_rules=None):
        return raw_text.capitalize()

    def execute_editing_command(self, command):
        return CommandResult.success()

    def verify_focus_target(self):
        return True

    def is_active(self):
        return True


class DummyContextService:
    def get_foreground_window(self):
        return 0x1000

    def get_focus_state(self):
        return FocusState(0x1000, 100, "app.exe", "Title", "Class")

    def is_password_focused(self):
        return False

    def is_secure_desktop(self):
        return False

    def get_displays(self):
        return []

    def subscribe_focus_changed(self, callback):
        pass

    def unsubscribe_focus_changed(self, callback):
        pass


class DummyCommandDispatcher:
    def dispatch(self, intent, cancellation_token=None):
        return CommandResult.success()

    def register_handler(self, action_name, handler):
        pass


class DummyElementActionService:
    def execute_action(self, element, action):
        return CommandResult.success()

    def supports_action(self, element, action):
        return True


class DummyAudioCaptureService:
    def start(self):
        pass

    def stop(self):
        pass

    def is_recording(self):
        return True

    def read_chunk(self):
        return None


class DummyFeedbackService:
    def play_earcon(self, cue_name):
        pass

    def show_hud_message(self, message, duration_ms=2000, level="info"):
        pass


def test_protocol_adherence():
    assert isinstance(DummySpeechEngine(), ISpeechEngine)
    assert isinstance(DummyOverlayService(), IOverlayService)
    assert isinstance(DummyInputInjector(), IInputInjector)
    assert isinstance(DummyElementProvider(), IElementProvider)
    assert isinstance(DummyCommandParser(), ICommandParser)
    assert isinstance(DummyDictationService(), IDictationService)
    assert isinstance(DummyContextService(), IContextService)
    assert isinstance(DummyCommandDispatcher(), ICommandDispatcher)
    assert isinstance(DummyElementActionService(), IElementActionService)
    assert isinstance(DummyAudioCaptureService(), IAudioCaptureService)
    assert isinstance(DummyFeedbackService(), IFeedbackService)
