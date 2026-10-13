"""
Unit tests for VoxPilot WindowsInputInjector (src/voxpilot/input/input_injector.py).
Tests:
- Triple click at (x, y) with Win32 multi-click timing
- Long press at (x, y, duration_s) with hold timing
- Smooth cosine-eased drag-and-drop triggering OLE IDropTarget
- Fail-safe modifier release and mouse button release upon interruption
- IInputInjector protocol compliance
"""

import math
from unittest.mock import MagicMock, call, patch
import pytest

from voxpilot.contracts.dto import MouseButton, ScrollDirection
from voxpilot.contracts.interfaces import IInputInjector
from voxpilot.input.input_injector import (
    WindowsInputInjector,
    MODIFIER_VKS,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MOVE,
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_VIRTUALDESK,
)


# ============================================================================
# Protocol Compliance Tests
# ============================================================================

def test_windows_input_injector_implements_protocol() -> None:
    injector = WindowsInputInjector()
    assert isinstance(injector, IInputInjector)


def test_protocol_mouse_move_delegation() -> None:
    injector = WindowsInputInjector()
    with patch.object(injector, "move_cursor") as mock_move:
        res = injector.mouse_move(150, 300)
        assert res is True
        mock_move.assert_called_once_with(150, 300)


def test_protocol_mouse_click_delegation() -> None:
    injector = WindowsInputInjector()
    with patch.object(injector, "click_at") as mock_click_at, \
         patch.object(injector, "click") as mock_click:
        # With coordinates
        res = injector.mouse_click(100, 200, button=MouseButton.RIGHT, count=2)
        assert res is True
        mock_click_at.assert_called_once_with(100, 200, button=MouseButton.RIGHT, count=2)
        mock_click.assert_not_called()

        # Without coordinates
        mock_click_at.reset_mock()
        res2 = injector.mouse_click(button=MouseButton.LEFT, count=1)
        assert res2 is True
        mock_click.assert_called_once_with(button=MouseButton.LEFT, count=1)
        mock_click_at.assert_not_called()


def test_protocol_mouse_drag_delegation() -> None:
    injector = WindowsInputInjector()
    with patch.object(injector, "drag_and_drop") as mock_dad:
        res = injector.mouse_drag(10, 20, 100, 200, duration_ms=500)
        assert res is True
        mock_dad.assert_called_once_with(10, 20, 100, 200, duration_s=0.5)


def test_protocol_mouse_scroll_delegation() -> None:
    injector = WindowsInputInjector()
    with patch.object(injector, "scroll") as mock_scroll:
        res = injector.mouse_scroll(delta_y=120, delta_x=-120)
        assert res is True
        assert mock_scroll.call_count == 2
        mock_scroll.assert_any_call(direction=ScrollDirection.UP, amount=120)
        mock_scroll.assert_any_call(direction=ScrollDirection.LEFT, amount=120)


# ============================================================================
# Triple Click Tests
# ============================================================================

def test_triple_click_at_sequence_and_timing() -> None:
    injector = WindowsInputInjector()
    recorded_events = []

    def mock_move(x, y, smooth=False, duration_ms=100):
        recorded_events.append(("move", x, y))

    def mock_down(button):
        recorded_events.append(("down", button))

    def mock_up(button):
        recorded_events.append(("up", button))

    recorded_sleeps = []
    def mock_sleep(s):
        recorded_sleeps.append(s)

    with patch.object(injector, "move_cursor", side_effect=mock_move), \
         patch.object(injector, "mouse_down", side_effect=mock_down), \
         patch.object(injector, "mouse_up", side_effect=mock_up), \
         patch("voxpilot.input.input_injector.time.sleep", side_effect=mock_sleep), \
         patch("voxpilot.input.input_injector.user32.GetDoubleClickTime", return_value=500):

        injector.triple_click_at(400, 300)

    # 1. Cursor moved to (400, 300)
    assert recorded_events[0] == ("move", 400, 300)

    # 2. Exactly 3 down-up sequences
    clicks = [(recorded_events[i], recorded_events[i + 1]) for i in range(1, len(recorded_events), 2)]
    assert len(clicks) == 3
    for down_ev, up_ev in clicks:
        assert down_ev == ("down", MouseButton.LEFT)
        assert up_ev == ("up", MouseButton.LEFT)

    # 3. Inter-click intervals are well within Win32 GetDoubleClickTime threshold (500ms)
    # The recorded sleeps include initial settling, 3 down holds (20ms each), and 2 inter-click pauses (<= 40ms)
    for s in recorded_sleeps:
        assert s < 0.5  # All delays under double-click threshold


def test_triple_click_at_failsafe_on_exception() -> None:
    injector = WindowsInputInjector()
    call_count = 0

    def mock_down(btn):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Interrupted during second click down")

    mock_up = MagicMock()
    mock_rel_mods = MagicMock()

    with patch.object(injector, "move_cursor"), \
         patch.object(injector, "mouse_down", side_effect=mock_down), \
         patch.object(injector, "mouse_up", mock_up), \
         patch.object(injector, "release_all_modifiers", mock_rel_mods), \
         patch("voxpilot.input.input_injector.time.sleep"):

        with pytest.raises(RuntimeError, match="Interrupted during second click down"):
            injector.triple_click_at(100, 100)

    # Fail-safe assertions:
    # First click had 1 normal up, second click threw during down so failsafe must ensure mouse_up & release_all_modifiers
    assert mock_up.call_count >= 1
    mock_rel_mods.assert_called_once()


def test_triple_click_at_failsafe_on_sleep_interrupt() -> None:
    injector = WindowsInputInjector()
    mock_up = MagicMock()
    mock_rel_mods = MagicMock()

    sleep_count = 0
    def mock_sleep(s):
        nonlocal sleep_count
        sleep_count += 1
        # Interrupt while button is held down (sleep_count == 2 is first press_delay)
        if sleep_count == 2:
            raise KeyboardInterrupt("Emergency user abort")

    with patch.object(injector, "move_cursor"), \
         patch.object(injector, "mouse_down"), \
         patch.object(injector, "mouse_up", mock_up), \
         patch.object(injector, "release_all_modifiers", mock_rel_mods), \
         patch("voxpilot.input.input_injector.time.sleep", side_effect=mock_sleep):

        with pytest.raises(KeyboardInterrupt, match="Emergency user abort"):
            injector.triple_click_at(200, 200)

    # Mouse button must have been released and modifiers cleaned up
    mock_up.assert_called_with(MouseButton.LEFT)
    mock_rel_mods.assert_called_once()


# ============================================================================
# Long Press Tests
# ============================================================================

def test_long_press_at_sequence() -> None:
    injector = WindowsInputInjector()
    events = []

    def mock_move(x, y, smooth=False, duration_ms=100):
        events.append(("move", x, y))

    def mock_down(button):
        events.append(("down", button))

    def mock_up(button):
        events.append(("up", button))

    sleep_durations = []
    def mock_sleep(s):
        sleep_durations.append(s)

    with patch.object(injector, "move_cursor", side_effect=mock_move), \
         patch.object(injector, "mouse_down", side_effect=mock_down), \
         patch.object(injector, "mouse_up", side_effect=mock_up), \
         patch("voxpilot.input.input_injector.time.sleep", side_effect=mock_sleep):

        injector.long_press_at(500, 600, duration_s=1.5)

    assert events[0] == ("move", 500, 600)
    assert events[1] == ("down", MouseButton.LEFT)
    assert events[2] == ("up", MouseButton.LEFT)
    # The hold sleep must match the requested duration
    assert 1.5 in sleep_durations


def test_long_press_at_failsafe_on_interrupt() -> None:
    injector = WindowsInputInjector()
    mock_up = MagicMock()
    mock_rel_mods = MagicMock()

    def mock_sleep(s):
        if s >= 1.0:
            raise KeyboardInterrupt("PTT Aborted")

    with patch.object(injector, "move_cursor"), \
         patch.object(injector, "mouse_down"), \
         patch.object(injector, "mouse_up", mock_up), \
         patch.object(injector, "release_all_modifiers", mock_rel_mods), \
         patch("voxpilot.input.input_injector.time.sleep", side_effect=mock_sleep):

        with pytest.raises(KeyboardInterrupt, match="PTT Aborted"):
            injector.long_press_at(300, 400, duration_s=1.0)

    # Button release and modifier cleanup guaranteed
    mock_up.assert_called_with(MouseButton.LEFT)
    mock_rel_mods.assert_called_once()


# ============================================================================
# Drag and Drop (Cosine Eased) Tests
# ============================================================================

def test_drag_and_drop_cosine_eased_trajectory() -> None:
    injector = WindowsInputInjector()
    moves = []
    button_events = []

    def mock_move(x, y, smooth=False, duration_ms=100):
        moves.append((x, y))

    def mock_down(btn):
        button_events.append(("down", btn))

    def mock_up(btn):
        button_events.append(("up", btn))

    with patch.object(injector, "move_cursor", side_effect=mock_move), \
         patch.object(injector, "mouse_down", side_effect=mock_down), \
         patch.object(injector, "mouse_up", side_effect=mock_up), \
         patch("voxpilot.input.input_injector.time.sleep"):

        injector.drag_and_drop(100, 200, 500, 600, duration_s=0.3)

    # 1. Initial move to start position (100, 200) before mouse down
    assert moves[0] == (100, 200)
    assert button_events[0] == ("down", MouseButton.LEFT)

    # 2. Final move reaches target (500, 600) before mouse up
    assert moves[-1] == (500, 600)
    assert button_events[1] == ("up", MouseButton.LEFT)

    # 3. Intermediate trajectory verification:
    # Cosine easing formula: p = (1 - cos(pi * t)) / 2
    # At t=0.5, p should be 0.5 (midpoint = (300, 400))
    # Easing starts with low velocity and ends with low velocity.
    intermediate_moves = moves[1:]  # trajectory steps
    assert len(intermediate_moves) >= 10

    # Middle step should be very close to the midpoint (300, 400)
    mid_idx = (len(intermediate_moves) - 1) // 2
    mid_x, mid_y = intermediate_moves[mid_idx]
    assert abs(mid_x - 300) <= 20
    assert abs(mid_y - 400) <= 20

    # Verify cosine easing acceleration profile:
    # Early delta (t=0.1) should be smaller than mid delta (t=0.5)
    first_delta = abs(intermediate_moves[1][0] - intermediate_moves[0][0])
    mid_delta = abs(intermediate_moves[mid_idx][0] - intermediate_moves[mid_idx - 1][0])
    assert first_delta <= mid_delta, "Cosine easing must accelerate from rest"


def test_drag_and_drop_failsafe_on_exception() -> None:
    injector = WindowsInputInjector()
    move_count = 0
    mock_up = MagicMock()
    mock_rel_mods = MagicMock()

    def mock_move(x, y, smooth=False, duration_ms=100):
        nonlocal move_count
        move_count += 1
        # Interrupted halfway through the drag movement
        if move_count == 10:
            raise RuntimeError("Drag cancelled by UIPI or timeout")

    with patch.object(injector, "move_cursor", side_effect=mock_move), \
         patch.object(injector, "mouse_down"), \
         patch.object(injector, "mouse_up", mock_up), \
         patch.object(injector, "release_all_modifiers", mock_rel_mods), \
         patch("voxpilot.input.input_injector.time.sleep"):

        with pytest.raises(RuntimeError, match="Drag cancelled by UIPI or timeout"):
            injector.drag_and_drop(0, 0, 500, 500, duration_s=0.3)

    # Fail-safe guarantees:
    mock_up.assert_called_with(MouseButton.LEFT)
    mock_rel_mods.assert_called_once()


def test_drag_and_drop_zero_duration() -> None:
    injector = WindowsInputInjector()
    mock_down = MagicMock()
    mock_up = MagicMock()
    moves = []

    with patch.object(injector, "move_cursor", side_effect=lambda x, y: moves.append((x, y))), \
         patch.object(injector, "mouse_down", mock_down), \
         patch.object(injector, "mouse_up", mock_up), \
         patch("voxpilot.input.input_injector.time.sleep"):

        injector.drag_and_drop(50, 50, 150, 150, duration_s=0.0)

    mock_down.assert_called_once_with(MouseButton.LEFT)
    mock_up.assert_called_once_with(MouseButton.LEFT)
    assert moves[0] == (50, 50)
    assert moves[-1] == (150, 150)


# ============================================================================
# Modifier and Mouse Button Cleanup Tests
# ============================================================================

def test_release_all_modifiers_sends_all_vks() -> None:
    injector = WindowsInputInjector()
    with patch("voxpilot.input.input_injector.user32.SendInput") as mock_send:
        injector.release_all_modifiers()
        assert mock_send.call_count == len(MODIFIER_VKS)


def test_release_all_mouse_buttons() -> None:
    injector = WindowsInputInjector()
    released_buttons = []

    with patch.object(injector, "mouse_up", side_effect=lambda b: released_buttons.append(b)):
        injector.release_all_mouse_buttons()

    assert MouseButton.LEFT in released_buttons
    assert MouseButton.RIGHT in released_buttons
    assert MouseButton.MIDDLE in released_buttons


def test_click_failsafe_on_exception() -> None:
    injector = WindowsInputInjector()
    mock_up = MagicMock()
    mock_rel_mods = MagicMock()

    with patch.object(injector, "mouse_down", side_effect=RuntimeError("Injection failed")), \
         patch.object(injector, "mouse_up", mock_up), \
         patch.object(injector, "release_all_modifiers", mock_rel_mods), \
         patch("voxpilot.input.input_injector.time.sleep"):

        with pytest.raises(RuntimeError):
            injector.click(count=2)

    mock_rel_mods.assert_called_once()
