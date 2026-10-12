"""Unit & Integration tests for extended commands: window snapping, chords, repeats, grid drill-down, and custom command loader."""

from unittest.mock import MagicMock
import pytest

from voxpilot.commands.command_parser import CommandParser
from voxpilot.commands.custom_commands_loader import CustomCommandLoader
from voxpilot.contracts.dto import CommandStatus, EngineMode, Intent, ScreenRect
from voxpilot.engine import VoxPilotEngine


def test_window_management_parsing() -> None:
    parser = CommandParser()

    cases = [
        ("snap left", "SNAP_WINDOW_LEFT"),
        ("snap window left", "SNAP_WINDOW_LEFT"),
        ("snap right", "SNAP_WINDOW_RIGHT"),
        ("snap window right", "SNAP_WINDOW_RIGHT"),
        ("snap up", "SNAP_WINDOW_UP"),
        ("snap top", "SNAP_WINDOW_UP"),
        ("snap down", "SNAP_WINDOW_DOWN"),
        ("snap bottom", "SNAP_WINDOW_DOWN"),
        ("switch app", "SWITCH_APP"),
        ("switch window", "SWITCH_APP"),
        ("task view", "TASK_VIEW"),
        ("next desktop", "NEXT_DESKTOP"),
        ("previous desktop", "PREVIOUS_DESKTOP"),
        ("page up", "PAGE_UP"),
        ("page down", "PAGE_DOWN"),
        ("zoom out", "UNDO_GRID"),
        ("undo grid", "UNDO_GRID"),
    ]

    for utterance, expected_intent in cases:
        intent = parser.parse(utterance)
        assert intent is not None, f"Failed to parse '{utterance}'"
        assert intent.name == expected_intent, f"Expected {expected_intent} for '{utterance}', got {intent.name}"


def test_keyboard_chord_and_repeat_parsing() -> None:
    parser = CommandParser()

    # Chords
    c1 = parser.parse("press ctrl shift t")
    assert c1 is not None and c1.name == "KEY_COMBINATION"
    assert c1.slots.get("keys") == ["ctrl", "shift", "t"]

    c2 = parser.parse("press alt f4")
    assert c2 is not None and c2.name == "KEY_COMBINATION"
    assert c2.slots.get("keys") == ["alt", "f4"]

    c3 = parser.parse("press ctrl w")
    assert c3 is not None and c3.name == "KEY_COMBINATION"
    assert c3.slots.get("keys") == ["ctrl", "w"]

    # Repeats
    r1 = parser.parse("press down 5 times")
    assert r1 is not None and r1.name == "KEY_REPEAT"
    assert r1.slots.get("key") == "down"
    assert r1.slots.get("count") == 5

    r2 = parser.parse("press tab 3 times")
    assert r2 is not None and r2.name == "KEY_REPEAT"
    assert r2.slots.get("key") == "tab"
    assert r2.slots.get("count") == 3

    r3 = parser.parse("press backspace ten times")
    assert r3 is not None and r3.name == "KEY_REPEAT"
    assert r3.slots.get("key") == "backspace"
    assert r3.slots.get("count") == 10


def test_grid_drill_down_parsing() -> None:
    parser = CommandParser()

    d1 = parser.parse("drill down 5")
    assert d1 is not None and d1.name == "DRILL_DOWN_GRID"
    assert d1.slots.get("cell") == 5

    d2 = parser.parse("zoom in 3")
    assert d2 is not None and d2.name == "DRILL_DOWN_GRID"
    assert d2.slots.get("cell") == 3


def test_custom_command_loader() -> None:
    loader = CustomCommandLoader()
    raw_config = {
        "commands": [
            {
                "trigger": "create new tab",
                "action_type": "hotkey",
                "action": ["ctrl", "t"],
                "description": "Opens new browser tab",
            },
            {
                "trigger": "insert my email",
                "action_type": "text",
                "action": "user@voxpilot.local",
                "description": "Inserts email",
            },
            {
                "trigger": "open editor",
                "action_type": "launch",
                "action": "notepad.exe",
                "scope_app": "explorer",
            },
            {
                "trigger": "format hard drive",
                "action_type": "launch",
                "action": "format C:",  # Dangerous!
            },
        ]
    }

    loaded = loader.load_from_dict(raw_config)
    # The dangerous command must be blocked!
    triggers = [c.trigger for c in loaded]
    assert "create new tab" in triggers
    assert "insert my email" in triggers
    assert "open editor" in triggers
    assert "format hard drive" not in triggers

    # App scoping check
    explorer_cmds = loader.get_matching_commands("explorer.exe")
    assert any(c.trigger == "open editor" for c in explorer_cmds)

    chrome_cmds = loader.get_matching_commands("chrome.exe")
    assert not any(c.trigger == "open editor" for c in chrome_cmds)
    assert any(c.trigger == "create new tab" for c in chrome_cmds)


def test_engine_extended_intent_execution() -> None:
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

    # Window snap left
    res = engine.execute_intent(Intent(name="SNAP_WINDOW_LEFT", raw_text="snap left"))
    assert res.status == CommandStatus.SUCCESS
    mock_input.key_combination.assert_called_with(["win", "left"])

    # Keyboard chord
    mock_input.reset_mock()
    res = engine.execute_intent(Intent(name="KEY_COMBINATION", slots={"keys": ["ctrl", "shift", "t"]}, raw_text="press ctrl shift t"))
    assert res.status == CommandStatus.SUCCESS
    mock_input.key_combination.assert_called_with(["ctrl", "shift", "t"])

    # Key repeat
    mock_input.reset_mock()
    res = engine.execute_intent(Intent(name="KEY_REPEAT", slots={"key": "down", "count": 4}, raw_text="press down 4 times"))
    assert res.status == CommandStatus.SUCCESS
    assert mock_input.key_press.call_count == 4

    # Grid drill down
    res = engine.execute_intent(Intent(name="DRILL_DOWN_GRID", slots={"cell": 7}, raw_text="drill down 7"))
    assert res.status == CommandStatus.SUCCESS
    mock_overlay.drill_down_grid.assert_called_with(7)

    # Grid cell click
    mock_overlay.is_grid_visible.return_value = True
    mock_overlay.get_grid_cell_center.return_value = (960, 540)
    mock_input.reset_mock()
    res = engine.execute_intent(Intent(name="CLICK_NUMBER", slots={"number": 5}, raw_text="5"))
    assert res.status == CommandStatus.SUCCESS
    mock_input.click_at.assert_called_with(960, 540, mock_input.click_at.call_args[0][2], 1)
    mock_overlay.hide_grid.assert_called_once()
