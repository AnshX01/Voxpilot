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
import atexit
import sys
import weakref
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
from voxpilot.overlay.grid_model import GridModel, Rect

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
        scr = QtWidgets.QApplication.primaryScreen()
        g = scr.geometry() if scr is not None else QtCore.QRect(0, 0, 1920, 1080)
        self.setGeometry(g)
        self.grid_model: Optional[GridModel] = None
        self.text_items: list = []  # (number, QRect) tuples for text numbers

        self.mode: OverlayMode = OverlayMode.OFF
        self.elements: List[LabeledElement] = []
        self.disambiguation_items: List[DisambiguationItem] = []
        self.grid_bounds: Optional[ScreenRect] = None
        self.grid_history: List[ScreenRect] = []
        self.grid_cells: int = 3
        self.grid_badge_cache: dict = {}

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

    # Apple Voice Control badge look (from guide screenshots): warm dark grey
    # rounded tag, bold white number, small pointer on the right edge.
    BADGE_BG = QtGui.QColor(74, 70, 66, 238)
    BADGE_EDGE = QtGui.QColor(255, 255, 255, 70)

    def _render_badge_pixmap(
        self,
        text: str,
        bg_color: QtGui.QColor = None,
        text_color: QtGui.QColor = QtGui.QColor(255, 255, 255),
        border_color: QtGui.QColor = None,
        pointer: bool = True,
    ) -> QtGui.QPixmap:
        bg_color = bg_color or self.BADGE_BG
        border_color = border_color or self.BADGE_EDGE
        font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold)
        fm = QtGui.QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        body_w = max(26, text_w + 14)
        tip = 7 if pointer else 0
        h = 22
        w = body_w + tip + 2
        pix = QtGui.QPixmap(w, h + 2)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setFont(font)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(1, 1, body_w, h - 2), 6, 6)
        if pointer:
            tri = QtGui.QPainterPath()
            tri.moveTo(body_w - 1, h / 2 - 5)
            tri.lineTo(body_w + tip, h / 2)
            tri.lineTo(body_w - 1, h / 2 + 5)
            tri.closeSubpath()
            path = path.united(tri)
        p.setBrush(QtGui.QColor(0, 0, 0, 70))
        p.setPen(QtCore.Qt.NoPen)
        p.translate(0, 1.5)
        p.drawPath(path)
        p.translate(0, -1.5)
        p.setBrush(bg_color)
        p.setPen(QtGui.QPen(border_color, 1.0))
        p.drawPath(path)
        p.setPen(text_color)
        p.drawText(QtCore.QRect(1, 1, body_w, h - 2), QtCore.Qt.AlignCenter, text)
        p.end()
        return pix

    def render_grid_badge(self, text: str, framed: bool) -> QtGui.QPixmap:
        font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold)
        fm = QtGui.QFontMetrics(font)
        w = max(24, fm.horizontalAdvance(text) + 12)
        h = 20
        pix = QtGui.QPixmap(w + 6, h + 6)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setFont(font)
        if framed:
            p.setBrush(QtCore.Qt.NoBrush)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 120), 2.0))
            p.drawRoundedRect(QtCore.QRectF(1, 1, w + 4, h + 4), 8, 8)
        p.setBrush(self.BADGE_BG)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 70), 1.0))
        p.drawRoundedRect(QtCore.QRectF(3, 3, w, h), 6, 6)
        p.setPen(QtGui.QColor(255, 255, 255))
        p.drawText(QtCore.QRect(3, 3, w, h), QtCore.Qt.AlignCenter, text)
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
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter: QtGui.QPainter) -> None:
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # 1. Number Badges Mode (Single-shot or Continuous)
        if self.mode in (OverlayMode.NUMBERS, OverlayMode.CONTINUOUS_NUMBERS):
            for el in self.elements:
                key = str(el.element_id)
                pix = self.badge_cache.get(key)
                if not pix:
                    pix = self._render_badge_pixmap(key)
                    self.badge_cache[key] = pix
                painter.drawPixmap(max(0, el.rect.x - pix.width() + 4), el.rect.y, pix)

        # 2. Name Badges Mode
        elif self.mode == OverlayMode.NAMES:
            for el in self.elements:
                name_text = el.name[:18] if el.name else f"Item {el.element_id}"
                pix = self.name_badge_cache.get(name_text)
                if not pix:
                    pix = self._render_badge_pixmap(name_text)
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

        # 4. Screen Grid Mode (Apple style: thin dark lines, centred framed badges)
        if self.mode == OverlayMode.GRID and self.grid_model is not None:
            gm = self.grid_model
            b = gm.bounds
            painter.setPen(QtGui.QPen(QtGui.QColor(40, 36, 32, 190), 1.0))
            for c in range(gm.cols + 1):
                x = b.x + round(c * b.w / gm.cols)
                painter.drawLine(x, b.y, x, b.y + b.h)
            for r in range(gm.rows + 1):
                y = b.y + round(r * b.h / gm.rows)
                painter.drawLine(b.x, y, b.x + b.w, y)
            framed = gm.framed()
            for n in range(1, gm.count + 1):
                cx, cy = gm.center(n)
                pix = self.grid_badge_cache.get((n, framed))
                if pix is None:
                    pix = self.render_grid_badge(str(n), framed)
                    self.grid_badge_cache[(n, framed)] = pix
                painter.drawPixmap(cx - pix.width() // 2, cy - pix.height() // 2, pix)

        # 4b. Text numbers (next to each line / word / character)
        if self.mode == OverlayMode.TEXT_NUMBERS:
            for num, qr in self.text_items:
                key = str(num)
                pix = self.badge_cache.get(key) or self._render_badge_pixmap(key)
                self.badge_cache[key] = pix
                painter.drawPixmap(max(0, qr.x() - pix.width() - 2), qr.y() + max(0, (qr.height() - pix.height()) // 2), pix)

        # 5. Recognised-command pill (Apple: small light italic pill under the menu bar)
        if self.hud_text:
            font_msg = QtGui.QFont("Segoe UI", 10)
            font_msg.setItalic(True)
            painter.setFont(font_msg)
            fm = QtGui.QFontMetrics(font_msg)
            msg = self.hud_text[:48]
            pw = fm.horizontalAdvance(msg) + 24
            ph = 26
            px = max(20, self.width() // 2 - pw - 60)
            py = 44
            painter.setBrush(QtGui.QColor(0, 0, 0, 50))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(px, py + 2, pw, ph, 7, 7)
            painter.setBrush(QtGui.QColor(236, 232, 228, 245))
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 25), 1))
            painter.drawRoundedRect(px, py, pw, ph, 7, 7)
            col = QtGui.QColor(60, 56, 52)
            if self.hud_level == "error":
                col = QtGui.QColor(170, 40, 40)
            painter.setPen(col)
            painter.drawText(QtCore.QRect(px, py, pw, ph), QtCore.Qt.AlignCenter, msg)


_LIVE_CANVASES: "weakref.WeakSet" = weakref.WeakSet()


def _shutdown_canvases() -> None:
    # Destroy overlay widgets before interpreter finalisation (avoids PySide teardown crash).
    for c in list(_LIVE_CANVASES):
        try:
            c.hide()
            for name in ("badge_cache", "name_badge_cache", "disambig_badge_cache", "grid_badge_cache"):
                getattr(c, name).clear()
            c.deleteLater()
        except Exception:
            pass
    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            app.processEvents()
        except Exception:
            pass


atexit.register(_shutdown_canvases)


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
        _LIVE_CANVASES.add(self._canvas)

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

    def hide_names(self) -> None:
        """Clear label name badges from the display."""
        if self._canvas:
            self._canvas.mode = OverlayMode.OFF
            self._current_mode = OverlayMode.OFF
            self._canvas.elements.clear()
            self._canvas.hide()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def is_names_visible(self) -> bool:
        """Check if name badges are currently visible."""
        return self._current_mode == OverlayMode.NAMES

    def show_grid(
        self,
        display_id: Optional[str] = None,
        sub_rect: Optional[ScreenRect] = None,
        cells: int = 3,
    ) -> None:
        """Show the Apple-style numbered grid (7x4 on screen, 5x5 per drill-down)."""
        if self._canvas:
            if sub_rect is not None:
                r = Rect(int(sub_rect.x), int(sub_rect.y), int(sub_rect.width), int(sub_rect.height))
            else:
                g = self._canvas.geometry()
                r = Rect(0, 0, g.width(), g.height())
            self._canvas.grid_model = GridModel(r)
            self._canvas.grid_bounds = ScreenRect(r.x, r.y, r.w, r.h)
            self._canvas.mode = OverlayMode.GRID
            self._current_mode = OverlayMode.GRID
            self._canvas.show()
            self._canvas.update()
            if self._app:
                self._app.processEvents()

    def show_text_numbers(self, items: list) -> None:
        """Badge numbers beside each text item. items: objects with .number and .rect (x,y,w,h) or None."""
        if not self._canvas:
            return
        self._canvas.text_items = [
            (it.number, QtCore.QRect(*it.rect)) for it in items if getattr(it, "rect", None)
        ]
        self._canvas.mode = OverlayMode.TEXT_NUMBERS
        self._current_mode = OverlayMode.TEXT_NUMBERS
        self._canvas.show()
        self._canvas.update()
        if self._app:
            self._app.processEvents()

    def hide_text_numbers(self) -> None:
        if self._current_mode == OverlayMode.TEXT_NUMBERS:
            self._canvas.text_items = []
            self.hide()

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
            self._canvas.grid_model = None
            self._canvas.text_items = []
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
        """Drill into a grid cell: shows a 5x5 grid there. None if the area can't be drilled further."""
        if self._current_mode != OverlayMode.GRID or not self._canvas or not self._canvas.grid_model:
            return None
        gm = self._canvas.grid_model
        if not gm.drill(cell_num):
            return None
        bnd = gm.bounds
        self._canvas.grid_bounds = ScreenRect(bnd.x, bnd.y, bnd.w, bnd.h)
        self._canvas.update()
        if self._app:
            self._app.processEvents()
        return self._canvas.grid_bounds

    def undo_grid(self) -> Optional[ScreenRect]:
        """Step back up one level in the grid drill-down hierarchy."""
        if not self._canvas or not self._canvas.grid_model or not self._canvas.grid_model.undo():
            return None
        bnd = self._canvas.grid_model.bounds
        self._canvas.grid_bounds = ScreenRect(bnd.x, bnd.y, bnd.w, bnd.h)
        self._canvas.update()
        if self._app:
            self._app.processEvents()
        return self._canvas.grid_bounds

    def can_drill_grid(self, cell_num: int) -> bool:
        gm = self._canvas.grid_model if self._canvas else None
        return bool(gm and gm.can_drill(cell_num))

    def grid_cell_count(self) -> int:
        gm = self._canvas.grid_model if self._canvas else None
        return gm.count if gm else 0

    def get_grid_cell_center(self, cell_num: int) -> Optional[tuple[int, int]]:
        """Screen centre of a cell in the active grid."""
        gm = self._canvas.grid_model if self._canvas else None
        return gm.center(cell_num) if gm else None

    # -------------------------------------------------------------------------
    # Backward Compatibility Aliases for Engine & Tests
    # -------------------------------------------------------------------------

    def set_refresh_callback(self, callback, interval_ms: int = 1200) -> None:
        """Call `callback` on the Qt GUI thread every interval while the app event loop runs."""
        if not self._canvas:
            return
        timer = getattr(self, "_refresh_timer", None)
        if timer is None:
            timer = QtCore.QTimer(self._canvas)
            self._refresh_timer = timer
        try:
            timer.timeout.disconnect()
        except Exception:
            pass
        timer.timeout.connect(callback)
        timer.start(interval_ms)

    def stop_refresh(self) -> None:
        """Stop the periodic refresh timer (before teardown, so no callback runs mid-hide)."""
        timer = getattr(self, "_refresh_timer", None)
        if timer is not None:
            try:
                timer.stop()
                timer.timeout.disconnect()
            except Exception:
                pass

    def show_commands_window(self, rows) -> None:
        """Show the floating Commands palette (voice command "Show commands")."""
        from voxpilot.app.commands_window import CommandsWindow
        self.hide_commands_window()
        self._commands_window = CommandsWindow(rows=list(rows))
        self._commands_window.show()

    def hide_commands_window(self) -> None:
        win = getattr(self, "_commands_window", None)
        if win is not None:
            win.close()
            self._commands_window = None

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


# -----------------------------------------------------------------------------
# GUI-thread marshalling: Qt widgets may only be touched from the thread that owns
# them. Speech/command handling runs on worker threads, so every mutating overlay
# call made from another thread is queued to the GUI thread and waited for.
# -----------------------------------------------------------------------------
class _GuiInvoker(QtCore.QObject):
    call = QtCore.Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.call.connect(self._run, QtCore.Qt.QueuedConnection)

    @QtCore.Slot(object)
    def _run(self, job) -> None:
        job()


def _marshal(fn):
    """Run `fn` on the GUI thread. Off-thread callers are queued to it only while the app's
    event loop is running (`gui_loop_running`). A queued job that has not started after the
    timeout is cancelled (never run later, never run on the calling thread); the call then
    returns None and logs. With no event loop (headless/tests) calls run in the caller's thread
    exactly as before, since there is no GUI thread to hand off to."""
    import functools

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        invoker = getattr(self, "_invoker", None)
        if (invoker is None or threading.get_ident() == self._gui_ident
                or not getattr(self, "gui_loop_running", False)):
            return fn(self, *args, **kwargs)
        state = {"claimed": False, "cancelled": False, "done": threading.Event(),
                 "result": None, "error": None}
        lock = threading.Lock()

        def job():
            with lock:
                if state["claimed"] or state["cancelled"]:
                    return
                state["claimed"] = True
            try:
                state["result"] = fn(self, *args, **kwargs)
            except BaseException as exc:  # pragma: no cover
                state["error"] = exc
            finally:
                state["done"].set()

        invoker.call.emit(job)
        if not state["done"].wait(3.0):
            with lock:
                if not state["claimed"]:
                    state["cancelled"] = True
                    logger.error("GUI thread did not service overlay call %s; dropped", fn.__name__)
                    return None
            state["done"].wait(10.0)  # already running on the GUI thread; wait for it
        if state["error"] is not None:
            raise state["error"]
        return state["result"]

    return wrapper


_orig_init_qt = OverlayService._init_qt


def _init_qt_with_invoker(self) -> None:
    _orig_init_qt(self)
    self._gui_ident = threading.get_ident()
    self._invoker = _GuiInvoker()


OverlayService._init_qt = _init_qt_with_invoker
for _name in (
    "show_numbers", "show_names", "hide_names", "show_grid", "show_text_numbers",
    "hide_text_numbers", "show_disambiguation", "show_hud", "hide", "hide_numbers",
    "hide_grid", "hide_all", "update_hud", "drill_down_grid", "undo_grid",
    "show_commands_window", "hide_commands_window",
):
    if hasattr(OverlayService, _name):
        setattr(OverlayService, _name, _marshal(getattr(OverlayService, _name)))
