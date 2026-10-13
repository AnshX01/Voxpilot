"""Command list shown by "Show commands" and the Commands window.

Content comes from the Apple guide (mh40719) command examples, limited to
commands this app implements. Lists vary by context like Apple's
("when writing a document, you see text formatting commands").
"""
from __future__ import annotations

from typing import Dict, List, Tuple

CATALOG: Dict[str, List[Tuple[str, str]]] = {
    "Basic Navigation": [
        ("Open <app name>", "Open an app, e.g. Open Mail"),
        ("Scroll up / Scroll down", "Scroll the active window"),
        ("Click <item name or number>", "Click an item, e.g. Click Done"),
        ("Move cursor <direction> <n> pixels", "e.g. Move cursor right 5 pixels"),
        ("Stop listening / Start listening", "Pause or resume Voice Control"),
        ("Show commands", "List available commands"),
        ("Open Voice Control Tutorial", "Practise essential commands"),
        ("Open document / Save document / New item", "Ctrl+O / Ctrl+S / Ctrl+N"),
        ("Next app / Previous app", "Alt+Tab / Alt+Shift+Tab"),
        ("Quit application / Hide application", "Alt+F4 / minimise"),
        ("Show keyboard / Hide keyboard", "Windows on-screen keyboard"),
        ("Repeat <n> times", "Repeat the previous command"),
    ],
    "Overlays": [
        ("Show names / Hide names", "Label items with their names"),
        ("Show numbers / Hide numbers", "Label items with numbers"),
        ("Show text numbers / Hide text numbers", "Number lines, words and characters in text"),
        ("Show grid / Hide grid", "Numbered screen grid"),
        ("Show window grid", "Grid over the active window only"),
        ("Drag <item> to <location>", "Drag and drop using names or numbers"),
    ],
    "Modes": [
        ("Dictation mode", "Words that aren't commands are entered as text (default)"),
        ("Spelling mode", "Enter text character by character; phonetic code words work"),
        ("Command mode", "Respond only to commands"),
        ("Swift mode", "Write Swift code by speaking it"),
    ],
    "Text editing": [
        ("Replace <old> with <new>", "e.g. Replace cat with dog"),
        ("Delete <n> / Uppercase <n>", "Act on a numbered line, word or character"),
        ("Select <n>", "Select a numbered text item"),
        ("Scratch that", "Undo the last dictated text"),
        ("Select all / Copy that / Cut that / Paste that", "Clipboard and selection"),
    ],
}


def character_rows() -> List[Tuple[str, str]]:
    """What to say for each character in Dictation / Spelling mode (guide: Commands > Dictation mode)."""
    from voxpilot.dictation.formatting import NATO_PHONETIC, PUNCTUATION_PHRASES
    rows: List[Tuple[str, str]] = []
    seen = set()
    for phrase, ch in PUNCTUATION_PHRASES:
        if phrase not in seen:
            seen.add(phrase)
            shown = {"\n": "new line", "\n\n": "new paragraph"}.get(ch, ch)
            rows.append((f"{phrase}  =  {shown}", "Say this to enter the character"))
    for word, ch in sorted(NATO_PHONETIC.items()):
        rows.append((f"{word}  =  {ch}", "Spelling mode code word"))
    return rows


def commands_for_context(ctx: str) -> List[Tuple[str, str, str]]:
    """Return (category, phrase, description) rows; text-editing first when typing."""
    order = ["Text editing", "Modes", "Overlays", "Basic Navigation"] if ctx == "text" else list(CATALOG)
    rows = [(cat, phrase, desc) for cat in order for phrase, desc in CATALOG[cat]]
    rows += [("Dictation and Spelling characters", p, d) for p, d in character_rows()]
    return rows
