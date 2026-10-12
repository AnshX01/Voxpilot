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
