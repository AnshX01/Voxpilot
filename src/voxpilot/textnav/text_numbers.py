"""Text numbers for Voice Control ("Show text numbers" / "Hide text numbers").

Apple guide (mh40719): in a text input area with numbers shown, a number is
displayed next to each line of text. Selecting a line or section shows a number
for each word in the selection; selecting a single word shows a number for each
character. Saying a command such as Delete or Uppercase followed by an item's
number acts on that item.

Pure logic: the focused control is reached through ITextTarget so this module
is testable without Windows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple
import re


class ITextTarget(Protocol):
    def get_text(self) -> str: ...
    def select_range(self, start: int, end: int) -> bool: ...
    def get_selection(self) -> Tuple[int, int]: ...


@dataclass(frozen=True)
class TextItem:
    number: int
    start: int
    end: int
    text: str
    rect: Optional[Tuple[int, int, int, int]] = None  # screen x, y, w, h


class TextNumbering:
    LEVELS = ("line", "word", "char")

    def __init__(self, target: ITextTarget) -> None:
        self.target = target
        self.visible = False
        self.level = "line"
        self.items: List[TextItem] = []
        self._scope: Tuple[int, int] = (0, 0)

    # -- state -------------------------------------------------------------
    def show(self) -> List[TextItem]:
        self.visible = True
        self.level = "line"
        text = self.target.get_text()
        self._scope = (0, len(text))
        self.items = self._split(text, 0, len(text), "line")
        return self.items

    def hide(self) -> None:
        self.visible = False
        self.items = []
        self.level = "line"

    def refresh(self) -> List[TextItem]:
        """Re-read the control (text may have changed after an edit)."""
        if not self.visible:
            return []
        text = self.target.get_text()
        s, e = self._scope
        if self.level == "line" or e > len(text):
            self._scope = (0, len(text))
            s, e = self._scope
            self.level = "line"
        self.items = self._split(text, s, e, self.level)
        return self.items

    # -- splitting ---------------------------------------------------------
    @staticmethod
    def _split(text: str, start: int, end: int, level: str) -> List[TextItem]:
        seg = text[start:end]
        spans: List[Tuple[int, int]] = []
        if level == "line":
            pos = 0
            for part in seg.splitlines(keepends=True):
                body = part.rstrip("\r\n")
                if body.strip():
                    spans.append((pos, pos + len(body)))
                pos += len(part)
        elif level == "word":
            spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", seg)]
        else:
            spans = [(i, i + 1) for i, ch in enumerate(seg) if not ch.isspace()]
        return [TextItem(i + 1, start + a, start + b, text[start + a:start + b]) for i, (a, b) in enumerate(spans)]

    # -- lookup ------------------------------------------------------------
    def get(self, number: int) -> Optional[TextItem]:
        for it in self.items:
            if it.number == number:
                return it
        return None

    # -- commands ----------------------------------------------------------
    def select(self, number: int) -> bool:
        """Select item; drill to words (from a line) or characters (from a word)."""
        it = self.get(number)
        if it is None:
            return False
        if not self.target.select_range(it.start, it.end):
            return False
        text = self.target.get_text()
        if self.level == "line":
            self.level = "word"
        elif self.level == "word":
            self.level = "char"
        self._scope = (it.start, it.end)
        self.items = self._split(text, it.start, it.end, self.level)
        return True

    def apply(self, op: str, number: int) -> bool:
        """op in delete|uppercase|lowercase|capitalize. Returns False if item missing."""
        it = self.get(number)
        if it is None:
            return False
        if not self.target.select_range(it.start, it.end):
            return False
        return True

    @staticmethod
    def transform(op: str, text: str) -> Optional[str]:
        if op == "delete":
            return ""
        if op == "uppercase":
            return text.upper()
        if op == "lowercase":
            return text.lower()
        if op == "capitalize":
            return text[:1].upper() + text[1:]
        return None
