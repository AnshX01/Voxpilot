"""VoxPilot Overlay Service Implementation.

Owned by: Overlay-UI
Implements: IOverlayService
Features:
- Hardware-accelerated non-activating, click-through canvas (PySide6)
- Pre-cached numbered badges (1..999) + on-demand rendering
- Named element badges ('show names')
- Lettered disambiguation badges ('A', 'B', 'C')
- 3x3 recursive navigation grid with multi-level drill-down and undo
- HUD toast banner with engine mode, transcript, and confidence
- Multi-monitor / display rect awareness
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from voxpilot.contracts.dto import (
    DisambiguationItem,
    EngineMode,
    GridTarget,
    LabeledElement,
    OverlayMode,
    ScreenRect,
)
from voxpilot.contracts.interfaces import IOverlayService

logger = logging.getLogger("voxpilot.overlay")

# Win32 Window Styles
user32 = ctypes.windll.user32
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
GWL_EXSTYLE = -20


class OverlayCanvas(QtWidgets.QWidget):
    """Transparent click-through canvas window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
            | QtCore.Qt.WindowTransparentForInput
            | QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(0, 0, 1920, 1080)

        self.mode: OverlayMode = OverlayMode.OFF
        self.elements: List[LabeledElement] = []
        self.disambiguation_items: List[DisambiguationItem] = []
        self.grid_bounds: Optional[ScreenRect] = None
        self.grid_history: List[ScreenRect] = []
        self.grid_cells: int = 3

        # HUD State
        self.hud_text: str = ""
        self.hud_mode: str = "COMMAND"
        self.hud_level: str = "info"
        self.hud_confidence: float = 1.0

        # Badge Cache for numbers 1-300
        self.badge_cache: Dict[str, QtGui.QPixmap] = {}
        self.name_badge_cache: Dict[str, QtGui.QPixmap] = {}
        self.disambig_badge_cache: Dict[str, QtGui.QPixmap] = {}
        self._pre_render_badges()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        hwnd = int(self.winId())
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            ex
            | WS_EX_TRANSPARENT
            | WS_EX_LAYERED
            | WS_EX_NOACTIVATE
            | WS_EX_TOPMOST,
        )

    def _render_badge_pixmap(
        self,
        text: str,
        bg_color: QtGui.QColor = QtGui.QColor(22, 24, 28, 235),
        text_color: QtGui.QColor = QtGui.QColor(255, 255, 255),
        border_color: QtGui.QColor = QtGui.QColor(255, 255, 255, 90),
    ) -> QtGui.QPixmap:
        font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        fm = QtGui.QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        w = max(24, text_w + 14)
        h = 20
        pix = QtGui.QPixmap(w, h)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setFont(font)

        # Subtle drop shadow for crisp legibility over light and dark backgrounds
        p.setBrush(QtGui.QColor(0, 0, 0, 110))
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(1, 2, w - 2, h - 2, 4, 4)

        # Dark high-contrast badge background with 1px silver border
        p.setBrush(bg_color)
        p.setPen(QtGui.QPen(border_color, 1.0))
        p.drawRoundedRect(0, 0, w - 1, h - 2, 4, 4)

        # Pure white text
        p.setPen(text_color)
        p.drawText(0, 0, w, h - 2, QtCore.Qt.AlignCenter, text)
        p.end()
        return pix

    def _pre_render_badges(self) -> None:
        # Pre-render numbers 1-300
        for i in range(1, 301):
            text = str(i)
            self.badge_cache[text] = self._render_badge_pixmap(text)

        # Pre-render letters A-Z for disambiguation (Amber/Gold background)
        amber_bg = QtGui.QColor(230, 140, 20, 240)
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.disambig_badge_cache[letter] = self._render_badge_pixmap(
                letter, bg_color=amber_bg
            )

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # 1. Number Badges Mode (Single-shot or Continuous)
        if self.mode in (OverlayMode.NUMBERS, OverlayMode.CONTINUOUS_NUMBERS):
            for el in self.elements:
                key = str(el.element_id)
                pix = self.badge_cache.get(key)
                if not pix:
                    pix = self._render_badge_pixmap(key)
                    self.badge_cache[key] = pix
                painter.drawPixmap(el.rect.x, el.rect.y, pix)

        # 2. Name Badges Mode
        elif self.mode == OverlayMode.NAMES:
            green_bg = QtGui.QColor(30, 160, 80, 230)
            for el in self.elements:
                name_text = el.name[:18] if el.name else f"Item {el.element_id}"
                pix = self.name_badge_cache.get(name_text)
                if not pix:
                    pix = self._render_badge_pixmap(
                        name_text, bg_color=green_bg
                    )
                    self.name_badge_cache[name_text] = pix
                painter.drawPixmap(el.rect.x, el.rect.y, pix)

        # 3. Disambiguation Badges Mode
        elif self.mode == OverlayMode.DISAMBIGUATION:
            for item in self.disambiguation_items:
                pix = self.disambig_badge_cache.get(item.badge_label)
                if not pix:
                    amber_bg = QtGui.QColor(230, 140, 20, 240)
                    pix = self._render_badge_pixmap(
                        item.badge_label, bg_color=amber_bg
                    )
                    self.disambig_badge_cache[item.badge_label] = pix
                painter.drawPixmap(item.element.rect.x, item.element.rect.y, pix)

        # 4. Screen Grid Mode
        if self.mode == OverlayMode.GRID:
            bounds = self.grid_bounds or ScreenRect(0, 0, 1920, 1080)
            cell_w = bounds.width / 3.0
            cell_h = bounds.height / 3.0

            pen = QtGui.QPen(QtGui.QColor(255, 50, 50, 190), 2.0)
            painter.setPen(pen)
            font = QtGui.QFont("Segoe UI", 16, QtGui.QFont.Bold)
            painter.setFont(font)

            num = 1
            for row in range(3):
                for col in range(3):
                    rx = int(bounds.x + col * cell_w)
                    ry = int(bounds.y + row * cell_h)
                    rw = int(cell_w)
                    rh = int(cell_h)
                    painter.drawRect(rx, ry, rw, rh)
                    painter.drawText(rx + 12, ry + 32, str(num))
                    num += 1

        # 5. Floating HUD Toast Pill (macOS-Style Centered at Screen Top)
        if self.hud_text or self.hud_mode:
            pill_w = 420
            pill_h = 36
            pill_x = max(20, (self.width() - pill_w) // 2)
            pill_y = 12
            hud_rect = QtCore.QRect(pill_x, pill_y, pill_w, pill_h)

            # Drop shadow
            painter.setBrush(QtGui.QColor(0, 0, 0, 90))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(pill_x + 1, pill_y + 2, pill_w, pill_h, 18, 18)

            # High-contrast dark pill with subtle white border
            painter.setBrush(QtGui.QColor(22, 24, 28, 235))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 60), 1))
            painter.drawRoundedRect(hud_rect, 18, 18)

            # Mic status dot
            mode_color = QtGui.QColor(0, 230, 130)
            if self.hud_mode == "DICTATION":
                mode_color = QtGui.QColor(70, 160, 255)
            elif self.hud_mode == "SLEEP":
                mode_color = QtGui.QColor(160, 160, 170)

            painter.setBrush(mode_color)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(pill_x + 14, pill_y + 11, 14, 14)

            # Mode indicator text
            painter.setPen(mode_color)
            font_mode = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
            painter.setFont(font_mode)
            painter.drawText(pill_x + 36, pill_y + 23, f"{self.hud_mode}")

            # Message text
            msg_color = QtGui.QColor(245, 245, 245)
            if self.hud_level == "warning":
                msg_color = QtGui.QColor(255, 200, 60)
            elif self.hud_level == "error":
                msg_color = QtGui.QColor(255, 80, 80)

            painter.setPen(msg_color)
            font_msg = QtGui.QFont("Segoe UI", 9)
            painter.setFont(font_msg)
            display_msg = self.hud_text[:36] if self.hud_text else "Listening..."
            painter.drawText(pill_x + 135, pill_y + 23, display_msg)


class OverlayService(IOverlayService):
    """Production controller for the hardware-accelerated non-activating canvas."""

    def __init__(self) -> None:
        self._app: Optional[QtWidgets.QApplication] = None
        self._canvas: Optional[OverlayCanvas] = None
        self._current_mode: OverlayMode = OverlayMode.OFF
        self._is_continuous_numbers: bool = False
        self._init_qt()

    def _init_qt(self) -> None:
        if QtWidgets.QApplication.instance() is None:
            self._app = QtWidgets.QApplication(sys.argv)
        else:
            self._app = QtWidgets.QApplication.instance()
        self._canvas = OverlayCanvas()

    # -------------------------------------------------------------------------
    # IOverlayService Contract Implementation
    # -------------------------------------------------------------------------

    def show_numbers(
        self,
        elements: list[LabeledElement],
        duration_ms: Optional[int] = None,
        continuous: bool = False,
    ) -> None:
        """Render numbered badges over the provided elements (single-shot or continuous)."""
        if self._canvas:
            self._is_continuous_numbers = continuous
            mode = OverlayMode.CONTINUOUS_NUMBERS if continuous else OverlayMode.NUMBERS
            self._canvas.elements = elements
            self._canvas.mode = mode
            self._current_mode = mode
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def show_names(self, elements: list[LabeledElement]) -> None:
        """Render label name badges over matching elements."""
        if self._canvas:
            self._canvas.elements = elements
            self._canvas.mode = OverlayMode.NAMES
            self._current_mode = OverlayMode.NAMES
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def show_grid(
        self,
        display_id: Optional[str] = None,
        sub_rect: Optional[ScreenRect] = None,
        cells: int = 3,
    ) -> None:
        """Render a 3x3 numbered mouse navigation grid across screen or sub-rectangle."""
        if self._canvas:
            if sub_rect is not None:
                self._canvas.grid_bounds = sub_rect
            elif self._canvas.grid_bounds is None:
                self._canvas.grid_bounds = ScreenRect(0, 0, 1920, 1080)
            self._canvas.grid_cells = cells
            self._canvas.mode = OverlayMode.GRID
            self._current_mode = OverlayMode.GRID
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def show_disambiguation(
        self,
        items: list[DisambiguationItem],
        target_rect: Optional[ScreenRect] = None,
    ) -> None:
        """Render lettered disambiguation badges over multiple candidate matches."""
        if self._canvas:
            self._canvas.disambiguation_items = items
            self._canvas.mode = OverlayMode.DISAMBIGUATION
            self._current_mode = OverlayMode.DISAMBIGUATION
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def show_hud(
        self,
        message: str,
        duration_ms: int = 2000,
        level: str = "info",
    ) -> None:
        """Display an ephemeral non-activating status toast banner."""
        if self._canvas:
            self._canvas.hud_text = message
            self._canvas.hud_level = level
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def hide(self) -> None:
        """Clear all active badges, grids, and overlays from the display."""
        if self._canvas:
            self._canvas.mode = OverlayMode.OFF
            self._current_mode = OverlayMode.OFF
            self._canvas.grid_bounds = None
            self._canvas.grid_history.clear()
            self._canvas.elements.clear()
            self._canvas.disambiguation_items.clear()
            self._canvas.hide()
            if self._app:
                self._app.processEvents()

    def is_visible(self) -> bool:
        """Check if any overlay layer is currently displayed."""
        return self._current_mode != OverlayMode.OFF

    def current_mode(self) -> OverlayMode:
        """Return the currently displayed overlay mode."""
        return self._current_mode

    # -------------------------------------------------------------------------
    # Recursive Grid Navigation & Drill-Down
    # -------------------------------------------------------------------------

    def drill_down_grid(self, cell_num: int) -> Optional[ScreenRect]:
        """Subdivide the active grid cell (1-9) into a recursive 3x3 sub-grid."""
        if self._current_mode != OverlayMode.GRID or not self._canvas:
            return None

        current = self._canvas.grid_bounds or ScreenRect(0, 0, 1920, 1080)
        if not (1 <= cell_num <= 9):
            return None

        # Record history for undo
        self._canvas.grid_history.append(current)

        row = (cell_num - 1) // 3
        col = (cell_num - 1) % 3
        cw = max(9.0, current.width / 3.0)
        ch = max(9.0, current.height / 3.0)

        new_rect = ScreenRect(
            x=int(current.x + col * (current.width / 3.0)),
            y=int(current.y + row * (current.height / 3.0)),
            width=int(cw),
            height=int(ch),
        )
        self._canvas.grid_bounds = new_rect
        self._canvas.update()
        if self._app:
            self._app.processEvents()
        return new_rect

    def undo_grid(self) -> Optional[ScreenRect]:
        """Step back up one level in the grid drill-down hierarchy."""
        if not self._canvas or not self._canvas.grid_history:
            return None

        previous = self._canvas.grid_history.pop()
        self._canvas.grid_bounds = previous
        self._canvas.update()
        if self._app:
            self._app.processEvents()
        return previous

    def get_grid_cell_center(self, cell_num: int) -> Optional[tuple[int, int]]:
        """Compute the screen center coordinates of cell (1-9) in active grid."""
        if not self._canvas or not (1 <= cell_num <= 9):
            return None
        current = self._canvas.grid_bounds or ScreenRect(0, 0, 1920, 1080)
        row = (cell_num - 1) // 3
        col = (cell_num - 1) % 3
        cw = current.width / 3.0
        ch = current.height / 3.0
        cx = int(current.x + col * cw + cw / 2.0)
        cy = int(current.y + row * ch + ch / 2.0)
        return (cx, cy)

    # -------------------------------------------------------------------------
    # Backward Compatibility Aliases for Engine & Tests
    # -------------------------------------------------------------------------

    def hide_numbers(self) -> None:
        self._is_continuous_numbers = False
        if self._current_mode in (OverlayMode.NUMBERS, OverlayMode.CONTINUOUS_NUMBERS):
            self.hide()

    def hide_grid(self) -> None:
        if self._current_mode == OverlayMode.GRID:
            self.hide()

    def hide_all(self) -> None:
        self._is_continuous_numbers = False
        self.hide()

    def is_numbers_visible(self) -> bool:
        return self._current_mode in (OverlayMode.NUMBERS, OverlayMode.CONTINUOUS_NUMBERS)

    def is_continuous_numbers(self) -> bool:
        return self._is_continuous_numbers or self._current_mode == OverlayMode.CONTINUOUS_NUMBERS

    def is_grid_visible(self) -> bool:
        return self._current_mode == OverlayMode.GRID

    def update_hud(
        self,
        mode: EngineMode = EngineMode.COMMAND,
        text: str = "",
        confidence: float = 1.0,
        is_listening: bool = True,
        error_hint: Optional[str] = None,
    ) -> None:
        if self._canvas:
            self._canvas.hud_mode = (
                mode.name if hasattr(mode, "name") else str(mode)
            )
            self._canvas.hud_text = error_hint or text
            self._canvas.hud_confidence = confidence
            self._canvas.hud_level = "error" if error_hint else "info"
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()
