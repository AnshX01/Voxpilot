"""Numbered screen grid model matching Apple Voice Control's grid.

Reference (Apple guide mh40719 screenshots): the full-screen grid is 7 columns
by 4 rows (cells numbered 1-28 left-to-right, top-to-bottom, badge at the cell
centre); saying a number drills into that cell and shows a 5 x 5 grid (1-25).
When an area can't be drilled further the badges are no longer framed and
saying a number performs the Click command. After any other command the grid
disappears.

Pure logic, no Qt, so it is testable on any platform.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

TOP_COLS, TOP_ROWS = 7, 4
DRILL_COLS, DRILL_ROWS = 5, 5
MIN_SUBCELL_PX = 56     # drilled grids are enlarged so 5x5 badges stay readable (inferred from Apple screenshot)
MIN_DRILLABLE_PX = 20   # a cell smaller than this can't be drilled; its number then clicks


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


class GridModel:
    def __init__(self, bounds: Rect) -> None:
        self.stack: List[Tuple[Rect, int, int]] = [(bounds, TOP_COLS, TOP_ROWS)]
        self.logical: List[Rect] = [bounds]  # un-enlarged screen area each level represents

    @property
    def bounds(self) -> Rect:
        return self.stack[-1][0]

    @property
    def cols(self) -> int:
        return self.stack[-1][1]

    @property
    def rows(self) -> int:
        return self.stack[-1][2]

    @property
    def count(self) -> int:
        return self.cols * self.rows

    def cell_rect(self, n: int) -> Optional[Rect]:
        if not 1 <= n <= self.count:
            return None
        b = self.bounds
        r, c = divmod(n - 1, self.cols)
        x0 = b.x + round(c * b.w / self.cols)
        x1 = b.x + round((c + 1) * b.w / self.cols)
        y0 = b.y + round(r * b.h / self.rows)
        y1 = b.y + round((r + 1) * b.h / self.rows)
        return Rect(x0, y0, x1 - x0, y1 - y0)

    def center(self, n: int) -> Optional[Tuple[int, int]]:
        cr = self.cell_rect(n)
        return None if cr is None else (cr.x + cr.w // 2, cr.y + cr.h // 2)

    def logical_cell(self, n: int) -> Optional[Rect]:
        lb = self.logical[-1]
        if not 1 <= n <= self.count:
            return None
        r, c = divmod(n - 1, self.cols)
        return Rect(lb.x + round(c * lb.w / self.cols), lb.y + round(r * lb.h / self.rows),
                    round(lb.w / self.cols), round(lb.h / self.rows))

    def can_drill(self, n: int) -> bool:
        lc = self.logical_cell(n)
        return lc is not None and lc.w >= MIN_DRILLABLE_PX and lc.h >= MIN_DRILLABLE_PX

    def drill(self, n: int) -> bool:
        if not self.can_drill(n):
            return False
        cr = self.cell_rect(n)
        root = self.stack[0][0]
        w = max(cr.w, DRILL_COLS * MIN_SUBCELL_PX)
        h = max(cr.h, DRILL_ROWS * MIN_SUBCELL_PX)
        cx, cy = cr.x + cr.w / 2, cr.y + cr.h / 2
        x = min(max(root.x, round(cx - w / 2)), root.x + root.w - w)
        y = min(max(root.y, round(cy - h / 2)), root.y + root.h - h)
        self.logical.append(self.logical_cell(n))
        self.stack.append((Rect(x, y, w, h), DRILL_COLS, DRILL_ROWS))
        return True

    def undo(self) -> bool:
        if len(self.stack) > 1:
            self.stack.pop()
            self.logical.pop()
            return True
        return False

    def framed(self) -> bool:
        """Badges are framed while numbers can still be drilled into."""
        return self.can_drill(1)
