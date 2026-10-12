"""
VoxPilot Overlay Service Implementation
Owned by: Overlay-UI
Implements: IOverlayService
"""

import sys
import threading
import time
import ctypes
from typing import Optional, List, Dict
from PySide6 import QtCore, QtGui, QtWidgets

from voxpilot.contracts.dto import LabeledElement, GridTarget, DisambiguationItem, EngineMode, ScreenRect

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
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool |
            QtCore.Qt.WindowTransparentForInput |
            QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(0, 0, 1920, 1080)

        self.elements: List[LabeledElement] = []
        self.show_numbers_flag: bool = False
        self.show_grid_flag: bool = False
        self.grid_bounds: Optional[ScreenRect] = None
        self.grid_cells: int = 3
        self.hud_text: str = ""
        self.hud_mode: str = "COMMAND"

        self.badge_cache: Dict[str, QtGui.QPixmap] = {}
        self._pre_render_badges()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        hwnd = int(self.winId())
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    def _render_badge_pixmap(self, text: str) -> QtGui.QPixmap:
        font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        bg = QtGui.QColor(24, 119, 242, 235)
        text_color = QtGui.QColor(255, 255, 255)
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0)

        w = max(24, 12 + len(text) * 8)
        h = 18
        pix = QtGui.QPixmap(w, h)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setFont(font)
        p.setPen(pen)
        p.setBrush(bg)
        p.drawRoundedRect(0, 0, w - 1, h - 1, 3, 3)
        p.setPen(text_color)
        p.drawText(0, 0, w, h, QtCore.Qt.AlignCenter, text)
        p.end()
        return pix

    def _pre_render_badges(self) -> None:
        for i in range(1, 300):
            text = str(i)
            self.badge_cache[text] = self._render_badge_pixmap(text)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw number badges
        if self.show_numbers_flag:
            for el in self.elements:
                key = str(el.element_id)
                pix = self.badge_cache.get(key)
                if not pix:
                    # FIX BUG-008: Render on-demand for element IDs >= 300
                    pix = self._render_badge_pixmap(key)
                    self.badge_cache[key] = pix
                painter.drawPixmap(el.rect.x, el.rect.y, pix)

        # Draw screen grid
        if self.show_grid_flag:
            bounds = self.grid_bounds or ScreenRect(0, 0, 1920, 1080)
            cell_w = bounds.width / 3.0
            cell_h = bounds.height / 3.0

            pen = QtGui.QPen(QtGui.QColor(255, 50, 50, 180), 2.0)
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
                    painter.drawText(rx + 10, ry + 30, str(num))
                    num += 1

        # Draw HUD bar at top right
        if self.hud_text or self.hud_mode:
            hud_rect = QtCore.QRect(1500, 10, 400, 36)
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 150), 1))
            painter.setBrush(QtGui.QColor(20, 20, 25, 220))
            painter.drawRoundedRect(hud_rect, 6, 6)

            painter.setPen(QtGui.QColor(0, 230, 120))
            font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
            painter.setFont(font)
            painter.drawText(1515, 33, f"[{self.hud_mode}]")

            painter.setPen(QtGui.QColor(240, 240, 240))
            font_msg = QtGui.QFont("Segoe UI", 9)
            painter.setFont(font_msg)
            display_msg = self.hud_text[:40] if self.hud_text else "Listening..."
            painter.drawText(1595, 33, display_msg)

class OverlayService:
    """Thread-safe controller for the transparent overlay canvas."""

    def __init__(self) -> None:
        self._app: Optional[QtWidgets.QApplication] = None
        self._canvas: Optional[OverlayCanvas] = None
        self._init_qt()

    def _init_qt(self) -> None:
        if QtWidgets.QApplication.instance() is None:
            self._app = QtWidgets.QApplication(sys.argv)
        else:
            self._app = QtWidgets.QApplication.instance()
        self._canvas = OverlayCanvas()

    def show_numbers(self, elements: List[LabeledElement], duration_ms: Optional[int] = None) -> None:
        if self._canvas:
            self._canvas.elements = elements
            self._canvas.show_numbers_flag = True
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def hide_numbers(self) -> None:
        if self._canvas:
            self._canvas.show_numbers_flag = False
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def show_grid(self, bounds: Optional[ScreenRect] = None, cells: int = 3) -> None:
        if self._canvas:
            self._canvas.grid_bounds = bounds
            self._canvas.grid_cells = cells
            self._canvas.show_grid_flag = True
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def hide_grid(self) -> None:
        if self._canvas:
            self._canvas.show_grid_flag = False
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def update_hud(
        self,
        mode: EngineMode = EngineMode.COMMAND,
        text: str = "",
        confidence: float = 1.0,
        is_listening: bool = True,
        error_hint: Optional[str] = None,
    ) -> None:
        if self._canvas:
            self._canvas.hud_mode = mode.name if hasattr(mode, "name") else str(mode)
            self._canvas.hud_text = error_hint or text
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def is_numbers_visible(self) -> bool:
        return bool(self._canvas and self._canvas.show_numbers_flag)

    def is_grid_visible(self) -> bool:
        return bool(self._canvas and self._canvas.show_grid_flag)

    def hide_all(self) -> None:
        if self._canvas:
            self._canvas.show_numbers_flag = False
            self._canvas.show_grid_flag = False
            self._canvas.hide()
            if self._app:
                self._app.processEvents()
