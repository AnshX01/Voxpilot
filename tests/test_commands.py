"""
Unit tests for Command-NLU module (NumberParser & CommandParser).
"""

import pytest
from voxpilot.commands import NumberParser, CommandParser
from voxpilot.contracts.dto import LabeledElement, ScreenRect

def test_number_parser_basic_ones():
    assert NumberParser.parse_number_phrase("zero") == 0
    assert NumberParser.parse_number_phrase("one") == 1
    assert NumberParser.parse_number_phrase("two") == 2
    assert NumberParser.parse_number_phrase("nine") == 9

def test_number_parser_homophones():
    assert NumberParser.parse_number_phrase("won") == 1
    assert NumberParser.parse_number_phrase("to") == 2
    assert NumberParser.parse_number_phrase("too") == 2
    assert NumberParser.parse_number_phrase("for") == 4
    assert NumberParser.parse_number_phrase("ate") == 8

def test_number_parser_teens_and_tens():
    assert NumberParser.parse_number_phrase("ten") == 10
    assert NumberParser.parse_number_phrase("eleven") == 11
    assert NumberParser.parse_number_phrase("twelve") == 12
    assert NumberParser.parse_number_phrase("nineteen") == 19
    assert NumberParser.parse_number_phrase("twenty") == 20
    assert NumberParser.parse_number_phrase("twenty three") == 23
    assert NumberParser.parse_number_phrase("forty two") == 42
    assert NumberParser.parse_number_phrase("ninety nine") == 99

def test_number_parser_hundreds():
    assert NumberParser.parse_number_phrase("one hundred") == 100
    assert NumberParser.parse_number_phrase("one hundred twenty three") == 123
    assert NumberParser.parse_number_phrase("five hundred fifty") == 550
    assert NumberParser.parse_number_phrase("nine hundred ninety nine") == 999

def test_number_parser_ordinals():
    assert NumberParser.parse_number_phrase("first") == 1
    assert NumberParser.parse_number_phrase("second") == 2
    assert NumberParser.parse_number_phrase("third") == 3
    assert NumberParser.parse_number_phrase("twelfth") == 12

def test_number_parser_digit_sequences():
    assert NumberParser.parse_number_phrase("2 3") == 23
    assert NumberParser.parse_number_phrase("1 2 3") == 123
    assert NumberParser.parse_number_phrase("42") == 42

def test_number_parser_invalid():
    assert NumberParser.parse_number_phrase("banana") is None
    assert NumberParser.parse_number_phrase("") is None
    assert NumberParser.parse_number_phrase("one thousand") is None

def test_command_parser_overlays():
    parser = CommandParser()
    intent = parser.parse("show numbers")
    assert intent is not None
    assert intent.name == "SHOW_NUMBERS"

    intent2 = parser.parse("please show numbers everywhere")
    assert intent2 is not None
    assert intent2.name == "SHOW_NUMBERS"

    intent3 = parser.parse("hide numbers")
    assert intent3 is not None
    assert intent3.name == "HIDE_NUMBERS"

    intent_grid = parser.parse("show grid")
    assert intent_grid is not None
    assert intent_grid.name == "SHOW_GRID"

def test_command_parser_click_number():
    parser = CommandParser()
    # Direct number
    intent = parser.parse("twenty three")
    assert intent is not None
    assert intent.name == "CLICK_NUMBER"
    assert intent.slots["number"] == 23

    # Click + number
    intent2 = parser.parse("click 42")
    assert intent2 is not None
    assert intent2.name == "CLICK_NUMBER"
    assert intent2.slots["number"] == 42

    intent3 = parser.parse("please click twelve")
    assert intent3 is not None
    assert intent3.name == "CLICK_NUMBER"
    assert intent3.slots["number"] == 12

def test_command_parser_click_name():
    parser = CommandParser()
    intent = parser.parse("click save")
    assert intent is not None
    assert intent.name == "CLICK_NAME"
    assert intent.slots["name"] == "save"

def test_command_parser_scroll():
    parser = CommandParser()
    intent = parser.parse("scroll down")
    assert intent is not None
    assert intent.name == "SCROLL"
    assert intent.slots["direction"] == "down"

    intent2 = parser.parse("scroll up 5")
    assert intent2 is not None
    assert intent2.slots["amount"] == 600

def test_command_parser_fuzzy_matching():
    parser = CommandParser()
    elem1 = LabeledElement(element_id=1, name="Save File", control_type="button", rect=ScreenRect(0, 0, 10, 10), window_handle=100)
    elem2 = LabeledElement(element_id=2, name="Cancel", control_type="button", rect=ScreenRect(0, 0, 10, 10), window_handle=100)
    elem3 = LabeledElement(element_id=3, name="Open Folder", control_type="button", rect=ScreenRect(0, 0, 10, 10), window_handle=100)

    matches = parser.fuzzy_match_element("save", [elem1, elem2, elem3])
    assert len(matches) > 0
    assert matches[0][0].name == "Save File"
    assert matches[0][1] >= 0.85
