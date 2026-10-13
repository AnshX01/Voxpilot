"""Focused text control access for Voice Control text numbers (Windows UIA).

API usage checked against uiautomation 2.0.29 source (TextRange.Move /
MoveEndpointByRange / MoveEndpointByUnit / Select / GetBoundingRectangles,
TextUnit.Character = 0, TextPatternRangeEndpoint.Start/End = 0/1).
Windows only; elsewhere every call fails soft. NOT run against a real
Windows control in this build.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

_CHAR = 0     # uiautomation.TextUnit.Character
_START = 0    # TextPatternRangeEndpoint.Start
_END = 1      # TextPatternRangeEndpoint.End


class FocusedTextTarget:
    def _focused(self):
        try:
            import uiautomation as auto
            return auto.GetFocusedControl()
        except Exception:
            return None

    @staticmethod
    def _text_pattern(c):
        if c is None:
            return None
        try:
            import uiautomation as auto
            return c.GetPattern(auto.PatternId.TextPattern)
        except Exception:
            return None

    def get_text(self) -> str:
        c = self._focused()
        tp = self._text_pattern(c)
        if tp is not None:
            try:
                return tp.DocumentRange.GetText(-1) or ""
            except Exception:
                pass
        try:
            return c.GetValuePattern().Value or ""
        except Exception:
            return ""

    @staticmethod
    def _range(tp, start: int, end: int):
        rng = tp.DocumentRange.Clone()
        # collapse to document start, then move to [start, end)
        rng.MoveEndpointByRange(_END, rng, _START)
        if start:
            rng.Move(_CHAR, start)
        rng.MoveEndpointByUnit(_END, _CHAR, max(0, end - start))
        return rng

    def select_range(self, start: int, end: int) -> bool:
        tp = self._text_pattern(self._focused())
        if tp is None:
            return False
        try:
            return bool(self._range(tp, start, end).Select())
        except Exception:
            return False

    def get_selection(self) -> Tuple[int, int]:
        return (0, 0)

    def item_rects(self, items) -> List[Optional[Tuple[int, int, int, int]]]:
        """Screen (x, y, w, h) of each item's first visible line fragment."""
        tp = self._text_pattern(self._focused())
        out: List[Optional[Tuple[int, int, int, int]]] = []
        for it in items:
            rect = None
            try:
                rs = self._range(tp, it.start, it.end).GetBoundingRectangles()
                if rs:
                    r = rs[0]
                    rect = (r.left, r.top, r.width(), r.height())
            except Exception:
                rect = None
            out.append(rect)
        return out
