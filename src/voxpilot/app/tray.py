"""VoxPilot Windows System Tray Application Controller.

Provides taskbar notification area presence, state toggles, and context menu.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional
from PySide6 import QtCore, QtGui, QtWidgets

from ..contracts.dto import EngineMode

logger = logging.getLogger("voxpilot.app.tray")


class VoxPilotTrayIcon(QtWidgets.QSystemTrayIcon):
    """System tray icon and menu for VoxPilot."""

    def __init__(
        self,
        engine: Any,
        parent: Optional[QtWidgets.QWidget] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        if QtWidgets.QApplication.instance() is None:
            self._app = QtWidgets.QApplication(["voxpilot"])
        else:
            self._app = QtWidgets.QApplication.instance()
        super().__init__(parent)
        self.engine = engine
        self.on_exit = on_exit

        self._create_icon()
        self._create_menu()
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_numbers()

    def _create_icon(self) -> None:
        """Generate a crisp high-DPI procedural tray icon."""
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw deep blue circle with cyan center
        painter.setBrush(QtGui.QColor(18, 90, 210))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)

        # Draw microphone glyph or 'V'
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2.5))
        painter.drawText(0, 0, 32, 32, QtCore.Qt.AlignCenter, "V")
        painter.end()

        self.setIcon(QtGui.QIcon(pixmap))
        self.setToolTip("VoxPilot Voice Control (Active)")

    # Apple Voice Control menu (guide screenshot): Voice Control / Stop Listening, Start Listening /
    # Mode: Dictation, Command, Spelling, Swift / Language: English / Microphone / Voice Control Settings...
    MODES = (
        ("Dictation Mode", EngineMode.DICTATION),
        ("Command Mode", EngineMode.COMMAND),
        ("Spelling Mode", EngineMode.SPELLING),
        ("Swift Mode", EngineMode.SWIFT),
    )

    _MENU_QSS = """
    QMenu { background: rgba(244,240,236,245); border: 1px solid rgba(0,0,0,40); border-radius: 12px;
            padding: 8px 6px; icon-size: 26px; font-family: 'Segoe UI'; font-size: 10.5pt; color: #1d1d1f; }
    QMenu::item { padding: 6px 22px 6px 10px; border-radius: 6px; margin: 1px 4px; }
    QMenu::item:selected { background: rgba(10,132,255,255); color: white; }
    QMenu::item:disabled { color: #8e8a86; }
    QMenu::separator { height: 1px; background: rgba(0,0,0,30); margin: 6px 14px; }
    QMenu::indicator { width: 18px; height: 18px; }
    """

    @staticmethod
    def _add_header(menu, text: str, title: bool = False):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(
            "padding: 4px 14px 2px 14px; background: transparent; "
            + ("font-weight: 700; color: #1d1d1f;" if title else "font-weight: 600; color: #6e6a66;")
        )
        wa = QtWidgets.QWidgetAction(menu)
        wa.setDefaultWidget(label)
        menu.addAction(wa)
        return wa

    @staticmethod
    def _speaker_icon(active: bool) -> QtGui.QIcon:
        px = QtGui.QPixmap(44, 44)
        px.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(px)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(10, 132, 255) if active else QtGui.QColor(215, 210, 205))
        p.drawEllipse(2, 2, 40, 40)
        fg = QtGui.QColor(255, 255, 255) if active else QtGui.QColor(70, 66, 62)
        p.setBrush(fg)
        poly = QtGui.QPolygonF([QtCore.QPointF(11, 18), QtCore.QPointF(17, 18), QtCore.QPointF(24, 12),
                                QtCore.QPointF(24, 32), QtCore.QPointF(17, 26), QtCore.QPointF(11, 26)])
        p.drawPolygon(poly)
        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(fg, 2.5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawArc(22, 14, 10, 16, -60 * 16, 120 * 16)
        p.end()
        return QtGui.QIcon(px)

    @staticmethod
    def _mode_icon(kind: str, active: bool) -> QtGui.QIcon:
        """Round icon like the guide's menu: blue circle when active, grey otherwise."""
        px = QtGui.QPixmap(44, 44)
        px.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(px)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(10, 132, 255) if active else QtGui.QColor(215, 210, 205))
        p.drawEllipse(2, 2, 40, 40)
        fg = QtGui.QColor(255, 255, 255) if active else QtGui.QColor(70, 66, 62)
        p.setPen(QtGui.QPen(fg, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        if kind == "mic":
            p.setBrush(fg)
            p.drawRoundedRect(18, 9, 8, 17, 4, 4)
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawArc(13, 14, 18, 17, 180 * 16, 180 * 16)
            p.drawLine(22, 31, 22, 36)
        elif kind == "move":
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                p.drawLine(22, 22, 22 + dx * 12, 22 + dy * 12)
                ex, ey = 22 + dx * 12, 22 + dy * 12
                p.drawLine(ex, ey, ex - dx * 4 + dy * 4, ey - dy * 4 + dx * 4)
                p.drawLine(ex, ey, ex - dx * 4 - dy * 4, ey - dy * 4 - dx * 4)
        else:
            f = QtGui.QFont("Segoe UI", 17, QtGui.QFont.Bold)
            p.setFont(f)
            p.drawText(QtCore.QRect(0, 0, 44, 44), QtCore.Qt.AlignCenter, "A" if kind == "a" else "S")
        p.end()
        return QtGui.QIcon(px)

    _MODE_ICON_KIND = {EngineMode.DICTATION: "mic", EngineMode.COMMAND: "move",
                       EngineMode.SPELLING: "a", EngineMode.SWIFT: "s"}

    def _refresh_mic_icons(self) -> None:
        for act in [self.mic_action] + list(getattr(self, "_mic_actions", [])):
            act.setIcon(self._speaker_icon(act.isChecked()))

    def _refresh_mode_icons(self) -> None:
        if hasattr(self, "mic_action"):
            self._refresh_mic_icons()
        for mode, act in self.mode_actions.items():
            act.setIcon(self._mode_icon(self._MODE_ICON_KIND[mode], act.isChecked()))

    def _create_menu(self) -> None:
        menu = QtWidgets.QMenu()
        self._menu = menu  # keep the Python wrapper alive; setContextMenu doesn't take ownership
        menu.setStyleSheet(self._MENU_QSS)
        self._add_header(menu, "Voice Control", title=True)
        menu.addSeparator()
        self.stop_action = menu.addAction("Stop Listening")
        self.stop_action.triggered.connect(self._stop_listening)
        self.start_action = menu.addAction("Start Listening")
        self.start_action.triggered.connect(self._start_listening)
        self.start_action.setEnabled(False)
        menu.addSeparator()
        self._add_header(menu, "Mode")
        self.mode_group = QtGui.QActionGroup(menu)
        self.mode_actions = {}
        for label, mode in self.MODES:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setActionGroup(self.mode_group)
            act.triggered.connect(lambda _=False, m=mode: self._set_mode(m))
            self.mode_actions[mode] = act
        self.mode_actions[EngineMode.DICTATION].setChecked(True)
        self.mode_group.triggered.connect(lambda _a: self._refresh_mode_icons())
        self._refresh_mode_icons()
        menu.addSeparator()
        self._add_header(menu, "Language")
        lang = menu.addAction("English")
        lang.setCheckable(True)
        lang.setChecked(True)
        menu.addSeparator()
        self._add_header(menu, "Microphone")
        self.mic_group = QtGui.QActionGroup(menu)
        self.mic_group.setExclusive(True)
        self.mic_action = menu.addAction("Automatic (default microphone)")
        self.mic_action.setCheckable(True)
        self.mic_action.setChecked(True)
        self.mic_action.triggered.connect(lambda _=False: self._select_microphone(None))
        self.mic_group.addAction(self.mic_action)
        self.mic_group.triggered.connect(lambda _a: self._refresh_mic_icons())
        self._refresh_mic_icons()
        self._mic_actions = []
        self._selected_mic = None
        menu.aboutToShow.connect(self.refresh_microphones)
        self._mic_anchor = menu.addSeparator()
        self.settings_action = menu.addAction("Voice Control Settings...")
        self.settings_action.triggered.connect(self._open_commands_window)
        menu.addSeparator()
        exit_action = menu.addAction("Quit VoxPilot")
        exit_action.triggered.connect(self._handle_exit)
        # kept for API compatibility (not shown in the Apple-style menu)
        self.status_action = QtGui.QAction("Status: Listening", self)
        self.listening_action = self.stop_action
        self.dictation_action = self.mode_actions[EngineMode.DICTATION]
        self.numbers_action = QtGui.QAction("Show Numbers", self)
        self.grid_action = QtGui.QAction("Show Grid", self)
        self.setContextMenu(menu)

    def _set_mode(self, mode: EngineMode) -> None:
        self.engine.mode = mode
        self.mode_actions[mode].setChecked(True)
        self._refresh_mode_icons()
        self.engine.overlay_service.update_hud(mode=mode, text=dict((m, l) for l, m in self.MODES)[mode])

    @staticmethod
    def list_input_devices() -> list:
        """Return [(device_index, name)] of distinct input devices (empty if unavailable)."""
        try:
            import sounddevice as sd
            seen, out = set(), []
            for idx, dev in enumerate(sd.query_devices()):
                name = str(dev.get("name", "")).strip()
                if dev.get("max_input_channels", 0) > 0 and name and name not in seen:
                    seen.add(name)
                    out.append((idx, name))
            return out
        except Exception:
            return []

    def refresh_microphones(self) -> None:
        menu = self._menu
        for act in self._mic_actions:
            menu.removeAction(act)
            self.mic_group.removeAction(act)
        self._mic_actions = []
        for idx, name in self.list_input_devices():
            act = QtGui.QAction(name, menu)
            act.setCheckable(True)
            act.setChecked(self._selected_mic == idx)
            act.triggered.connect(lambda _=False, i=idx: self._select_microphone(i))
            self.mic_group.addAction(act)
            menu.insertAction(self._mic_anchor, act)
            self._mic_actions.append(act)
        self.mic_action.setChecked(self._selected_mic is None)
        self._refresh_mic_icons()

    def _select_microphone(self, device_id) -> None:
        self._selected_mic = device_id
        try:
            self.engine.stop_live_capture()
            self.engine.start_live_capture(device_id=device_id)
        except Exception:
            pass

    def _stop_listening(self) -> None:
        self._prior_mode = self.engine.mode
        self.engine.mode = EngineMode.SLEEP
        self.stop_action.setEnabled(False)
        self.start_action.setEnabled(True)
        self.engine.overlay_service.hide_all()
        self.engine.overlay_service.update_hud(mode=self.engine.mode, text="Stop listening")

    def _start_listening(self) -> None:
        self.engine.mode = getattr(self, "_prior_mode", EngineMode.DICTATION)
        if self.engine.mode == EngineMode.SLEEP:
            self.engine.mode = EngineMode.DICTATION
        self.stop_action.setEnabled(True)
        self.start_action.setEnabled(False)
        self.mode_actions.get(self.engine.mode, self.mode_actions[EngineMode.DICTATION]).setChecked(True)
        self._refresh_mode_icons()
        self.engine.overlay_service.update_hud(mode=self.engine.mode, text="Start listening")

    def _open_commands_window(self) -> None:
        from .commands_window import CommandsWindow
        self._cmd_window = CommandsWindow(self.engine)
        self._cmd_window.show()

    def _toggle_listening(self) -> None:
        if self.engine.mode == EngineMode.SLEEP:
            self._start_listening()
        else:
            self._stop_listening()

    def _toggle_dictation(self) -> None:
        self._set_mode(EngineMode.COMMAND if self.engine.mode == EngineMode.DICTATION else EngineMode.DICTATION)

    def _toggle_numbers(self) -> None:
        if self.engine.overlay_service.is_numbers_visible():
            self.engine.overlay_service.hide_numbers()
            self.numbers_action.setText("Show Numbers")
        else:
            from ..contracts.dto import Intent
            self.engine._handle_show_numbers(Intent(name="SHOW_NUMBERS"))
            self.numbers_action.setText("Hide Numbers")

    def _toggle_grid(self) -> None:
        if self.engine.overlay_service.is_grid_visible():
            self.engine.overlay_service.hide_grid()
            self.grid_action.setText("Show Grid")
        else:
            self.engine.overlay_service.show_grid()
            self.grid_action.setText("Hide Grid")

    def _handle_exit(self) -> None:
        logger.info("Tray exit requested.")
        if self.on_exit:
            self.on_exit()
        QtWidgets.QApplication.quit()


def main() -> int:
    """Launch VoxPilot system tray application."""
    import argparse
    import signal
    import sys
    from ..engine import VoxPilotEngine

    parser = argparse.ArgumentParser(description="VoxPilot Voice Control System Tray App")
    parser.add_argument("--no-mic", action="store_true", help="Start without live microphone capture")
    parser.add_argument("--device", type=int, default=None, help="Audio input device index")
    args, _ = parser.parse_known_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    logger.info("Initializing VoxPilot Engine...")
    engine = VoxPilotEngine()
    engine.start(live_mic=not args.no_mic, device_id=args.device)

    def on_exit() -> None:
        logger.info("Shutting down VoxPilot...")
        engine.stop()

    tray = VoxPilotTrayIcon(engine=engine, on_exit=on_exit)
    tray.show()

    # Periodic timer to allow Python signal handling (Ctrl+C) in Qt event loop
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    def signal_handler(*_: Any) -> None:
        logger.info("Termination signal received. Exiting...")
        on_exit()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    try:
        signal.signal(signal.SIGTERM, signal_handler)
    except Exception:
        pass

    logger.info("VoxPilot is active and running in the system tray. Press Ctrl+C or right-click the tray icon to exit.")
    if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        tray.showMessage(
            "VoxPilot Voice Control",
            "VoxPilot is running and listening. Say 'show numbers' or right-click for options.",
            QtWidgets.QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    return app.exec()


if __name__ == "__main__":
    import sys

    sys.exit(main())

