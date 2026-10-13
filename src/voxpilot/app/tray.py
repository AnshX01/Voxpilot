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

    def _create_menu(self) -> None:
        """Build right-click context menu."""
        menu = QtWidgets.QMenu()

        # Status item
        self.status_action = menu.addAction("Status: Listening")
        self.status_action.setEnabled(False)
        menu.addSeparator()

        # Mode toggles
        self.listening_action = menu.addAction("Sleep (Stop Listening)")
        self.listening_action.triggered.connect(self._toggle_listening)

        self.dictation_action = menu.addAction("Switch to Dictation Mode")
        self.dictation_action.triggered.connect(self._toggle_dictation)

        menu.addSeparator()

        # Overlay toggles
        self.numbers_action = menu.addAction("Show Numbers")
        self.numbers_action.triggered.connect(self._toggle_numbers)

        self.grid_action = menu.addAction("Show Grid")
        self.grid_action.triggered.connect(self._toggle_grid)

        menu.addSeparator()

        # Exit action
        exit_action = menu.addAction("Exit VoxPilot")
        exit_action.triggered.connect(self._handle_exit)

        self.setContextMenu(menu)

    def _toggle_listening(self) -> None:
        if self.engine.mode == EngineMode.SLEEP:
            self.engine.mode = EngineMode.COMMAND
            self.listening_action.setText("Sleep (Stop Listening)")
            self.status_action.setText("Status: Listening")
            self.engine.overlay_service.update_hud(mode=self.engine.mode, text="Listening")
        else:
            self.engine.mode = EngineMode.SLEEP
            self.listening_action.setText("Wake Up (Start Listening)")
            self.status_action.setText("Status: Sleeping")
            self.engine.overlay_service.hide_all()
            self.engine.overlay_service.update_hud(mode=self.engine.mode, text="Sleeping")

    def _toggle_dictation(self) -> None:
        if self.engine.mode == EngineMode.DICTATION:
            self.engine.mode = EngineMode.COMMAND
            self.dictation_action.setText("Switch to Dictation Mode")
            self.engine.overlay_service.update_hud(mode=self.engine.mode, text="Command Mode")
        else:
            self.engine.mode = EngineMode.DICTATION
            self.dictation_action.setText("Switch to Command Mode")
            self.engine.overlay_service.update_hud(mode=self.engine.mode, text="Dictation Mode")

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

