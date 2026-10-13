"""Voice Control settings window, laid out like Apple's "Change Voice Control settings" page.

Option order (from the guide): Voice Control, Language, Microphone, Show hints, Play sound when command is
recognized, Overlay, Fade overlay after inactivity, Voice Control Tutorial, Commands, Vocabulary, Advanced
Actions menu. "Improve assistive voice features" (Apple data sharing) is intentionally not offered:
VoxPilot sends nothing anywhere.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .command_catalog import CATALOG, character_rows
from .commands_window import Tutorial
from .settings_store import (ACTION_TYPES, OVERLAY_CHOICES, VoiceControlSettings, export_custom_commands,
                             import_custom_commands)


class NewCommandDialog(QtWidgets.QDialog):
    """Apple's "Create your own commands": When I say / While using / Perform."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Voice Control Command")
        form = QtWidgets.QFormLayout(self)
        self.when = QtWidgets.QLineEdit()
        self.when.setPlaceholderText("Use <text> or <number> for variable parts")
        self.app = QtWidgets.QComboBox()
        self.app.addItem("Any Application")
        self.app.setEnabled(False)  # per-app commands are not supported (stated honestly in the tooltip)
        self.app.setToolTip("Commands apply in any application")
        self.action = QtWidgets.QComboBox()
        self.action.addItems(ACTION_TYPES)
        self.value = QtWidgets.QLineEdit()
        self.value.setPlaceholderText("Text, shortcut such as ctrl+shift+t, URL, or app name")
        form.addRow("When I say:", self.when)
        form.addRow("While using:", self.app)
        form.addRow("Perform:", self.action)
        form.addRow("", self.value)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        bb.button(QtWidgets.QDialogButtonBox.Ok).setText("Done")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def result_command(self) -> Optional[dict]:
        when = self.when.text().strip()
        if not when:
            return None
        return {"when_i_say": when, "action": self.action.currentText(), "value": self.value.text()}


class CommandsDialog(QtWidgets.QDialog):
    """Commands: searchable list (Custom first, then standard categories), preview area, Add / Remove."""

    def __init__(self, settings: VoiceControlSettings, on_change: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Commands")
        self.settings = settings
        self.on_change = on_change
        self.resize(640, 460)
        lay = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Show commands for:"))
        lang = QtWidgets.QComboBox()
        lang.addItem("English")
        top.addWidget(lang)
        top.addStretch(1)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search)
        lay.addLayout(top)
        split = QtWidgets.QSplitter()
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setTextElideMode(QtCore.Qt.ElideNone)
        self.tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.tree.setAlternatingRowColors(True)
        self.tree.currentItemChanged.connect(self._preview)
        self.preview = QtWidgets.QTextBrowser()
        split.addWidget(self.tree)
        split.addWidget(self.preview)
        split.setSizes([300, 320])
        lay.addWidget(split, 1)
        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+")
        add.setFixedWidth(34)
        add.clicked.connect(self._add)
        rem = QtWidgets.QPushButton("\u2212")
        rem.setFixedWidth(34)
        rem.clicked.connect(self._remove)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)
        self._populate()

    def _populate(self) -> None:
        self.tree.clear()
        custom = QtWidgets.QTreeWidgetItem(["Custom"])
        self.tree.addTopLevelItem(custom)
        for i, c in enumerate(self.settings.custom_commands):
            it = QtWidgets.QTreeWidgetItem([c["when_i_say"]])
            it.setData(0, QtCore.Qt.UserRole, ("custom", i))
            it.setData(0, QtCore.Qt.UserRole + 1, f'{c["action"]}: {c.get("value", "")}')
            custom.addChild(it)
        for cat, items in CATALOG.items():
            top = QtWidgets.QTreeWidgetItem([cat])
            self.tree.addTopLevelItem(top)
            for phrase, desc in items:
                for single in phrase.split(" / "):  # one row per spoken command, like Apple's list
                    it = QtWidgets.QTreeWidgetItem([single])
                    it.setToolTip(0, single)
                    it.setData(0, QtCore.Qt.UserRole + 1, desc)
                    top.addChild(it)
        chars = QtWidgets.QTreeWidgetItem(["Dictation and Spelling characters"])
        self.tree.addTopLevelItem(chars)
        for phrase, desc in character_rows():
            it = QtWidgets.QTreeWidgetItem([phrase])
            it.setData(0, QtCore.Qt.UserRole + 1, desc)
            chars.addChild(it)
        self.tree.expandItem(custom)
        self.tree.expandItem(self.tree.topLevelItem(1))

    def _filter(self, text: str) -> None:
        text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            shown = 0
            for j in range(top.childCount()):
                match = not text or text in top.child(j).text(0).lower()
                top.child(j).setHidden(not match)
                shown += match
            top.setHidden(bool(text) and shown == 0)
            if text and shown:
                top.setExpanded(True)

    def _preview(self, cur, _prev) -> None:
        if cur is None or cur.parent() is None:
            self.preview.clear()
            return
        self.preview.setHtml(f"<h3>{cur.text(0)}</h3><p>{cur.data(0, QtCore.Qt.UserRole + 1) or ''}</p>")

    def _add(self) -> None:
        dlg = NewCommandDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            cmd = dlg.result_command()
            if cmd:
                self.settings.custom_commands.append(cmd)
                self._commit()

    def _remove(self) -> None:
        cur = self.tree.currentItem()
        data = cur.data(0, QtCore.Qt.UserRole) if cur else None
        if data and data[0] == "custom":
            del self.settings.custom_commands[data[1]]
            self._commit()

    def _commit(self) -> None:
        self.on_change()
        self._populate()


class VocabularyDialog(QtWidgets.QDialog):
    """Vocabulary: words or phrases you added, with Add / Remove."""

    def __init__(self, settings: VoiceControlSettings, on_change: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vocabulary")
        self.settings = settings
        self.on_change = on_change
        self.resize(360, 320)
        lay = QtWidgets.QVBoxLayout(self)
        self.list = QtWidgets.QListWidget()
        self.list.addItems(settings.vocabulary)
        lay.addWidget(self.list, 1)
        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+")
        add.setFixedWidth(34)
        add.clicked.connect(self._add)
        rem = QtWidgets.QPushButton("\u2212")
        rem.setFixedWidth(34)
        rem.clicked.connect(self._remove)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)

    def _add(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(self, "Vocabulary", "Word or phrase:")
        if ok and text.strip():
            self.settings.vocabulary.append(text.strip())
            self.list.addItem(text.strip())
            self.on_change()

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            del self.settings.vocabulary[row]
            self.list.takeItem(row)
            self.on_change()


class VoiceControlSettingsWindow(QtWidgets.QWidget):
    def __init__(self, engine, hooks: Optional[dict] = None, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.hooks = hooks or {}
        self.settings: VoiceControlSettings = engine.settings
        self.setWindowTitle("Voice Control")
        self.resize(520, 470)
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(24, 20, 24, 20)
        form.setVerticalSpacing(12)
        self.enabled = QtWidgets.QCheckBox()
        self.enabled.setChecked(engine.mode.value != "sleep")
        self.enabled.toggled.connect(self._toggle_listening)
        form.addRow("Voice Control", self.enabled)
        self.language = QtWidgets.QComboBox()
        self.language.addItem("English")
        form.addRow("Language", self.language)
        self.mic = QtWidgets.QComboBox()
        self.mic.addItem("Automatic")
        for _idx, name in (self.hooks.get("list_mics") or (lambda: []))():
            self.mic.addItem(name)
        i = self.mic.findText(self.settings.microphone)
        self.mic.setCurrentIndex(max(i, 0))
        self.mic.currentTextChanged.connect(self._mic_changed)
        form.addRow("Microphone", self.mic)
        self.hints = QtWidgets.QCheckBox()
        self.hints.setChecked(self.settings.show_hints)
        self.hints.toggled.connect(lambda v: self._set("show_hints", v))
        form.addRow("Show hints", self.hints)
        self.sound = QtWidgets.QCheckBox()
        self.sound.setChecked(self.settings.play_sound)
        self.sound.toggled.connect(lambda v: self._set("play_sound", v))
        form.addRow("Play sound when command is recognized", self.sound)
        self.overlay = QtWidgets.QComboBox()
        self.overlay.addItems(OVERLAY_CHOICES)
        self.overlay.setCurrentText(self.settings.overlay)
        self.overlay.currentTextChanged.connect(lambda v: self._set("overlay", v))
        form.addRow("Overlay", self.overlay)
        fade = QtWidgets.QWidget()
        fl = QtWidgets.QHBoxLayout(fade)
        fl.setContentsMargins(0, 0, 0, 0)
        self.fade = QtWidgets.QCheckBox()
        self.fade.setChecked(self.settings.fade_overlay)
        self.fade.toggled.connect(lambda v: self._set("fade_overlay", v))
        self.fade_secs = QtWidgets.QSpinBox()
        self.fade_secs.setRange(1, 600)
        self.fade_secs.setSuffix(" s")
        self.fade_secs.setValue(self.settings.fade_after_seconds)
        self.fade_secs.valueChanged.connect(lambda v: self._set("fade_after_seconds", int(v)))
        self.fade_amt = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.fade_amt.setRange(10, 95)
        self.fade_amt.setValue(int(self.settings.fade_amount * 100))
        self.fade_amt.valueChanged.connect(lambda v: self._set("fade_amount", v / 100.0))
        fl.addWidget(self.fade)
        fl.addWidget(self.fade_secs)
        fl.addWidget(self.fade_amt, 1)
        form.addRow("Fade overlay after inactivity", fade)
        tut = QtWidgets.QPushButton("Open Tutorial...")
        tut.clicked.connect(self._open_tutorial)
        form.addRow("Voice Control Tutorial", tut)
        cmds = QtWidgets.QPushButton("Commands...")
        cmds.clicked.connect(lambda: CommandsDialog(self.settings, self._changed, self).exec())
        form.addRow("Commands", cmds)
        voc = QtWidgets.QPushButton("Vocabulary...")
        voc.clicked.connect(lambda: VocabularyDialog(self.settings, self._changed, self).exec())
        form.addRow("Vocabulary", voc)
        adv = QtWidgets.QToolButton()
        adv.setText("\u2026")
        adv.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(adv)
        menu.addAction("Import Custom Commands...").triggered.connect(self._import)
        menu.addAction("Export Custom Commands...").triggered.connect(self._export)
        menu.addAction("Delete All Custom Commands").triggered.connect(self._delete_all)
        adv.setMenu(menu)
        form.addRow("Advanced Actions", adv)

    def showEvent(self, ev) -> None:  # noqa: N802
        """Reflect what the tray did meanwhile (Stop/Start Listening)."""
        self.enabled.blockSignals(True)
        self.enabled.setChecked(self.engine.mode.value != "sleep")
        self.enabled.blockSignals(False)
        current = (self.hooks.get("current_mic") or (lambda: None))()
        if current:
            i = self.mic.findText(current)
            if i >= 0:
                self.mic.blockSignals(True)
                self.mic.setCurrentIndex(i)
                self.mic.blockSignals(False)
                self.settings.microphone = current  # keep the saved choice equal to what the tray is using
                try:
                    self.settings.save()
                except OSError:
                    pass
        super().showEvent(ev)

    # -- actions -------------------------------------------------------------------------------
    def _set(self, name: str, value) -> None:
        setattr(self.settings, name, value)
        self._changed()

    def _changed(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass
        self.engine.apply_settings(self.settings)

    def _toggle_listening(self, on: bool) -> None:
        cb = self.hooks.get("set_listening")
        if cb:
            cb(on)

    def _mic_changed(self, name: str) -> None:
        self.settings.microphone = name
        cb = self.hooks.get("select_mic")
        if cb:
            cb(name)
        self._changed()

    def _open_tutorial(self) -> None:
        self._tutorial = Tutorial(self.engine, self)
        self._tutorial.show()

    def _import(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Custom Commands", "", "JSON (*.json)")
        if path:
            try:
                import_custom_commands(self.settings, path)
            except (OSError, ValueError):
                QtWidgets.QMessageBox.warning(self, "Import Custom Commands", "That file could not be imported.")
                return
            self._changed()

    def _export(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Custom Commands", "voice-control-commands.json",
                                                        "JSON (*.json)")
        if path:
            export_custom_commands(self.settings, path)

    def _delete_all(self) -> None:
        if QtWidgets.QMessageBox.question(self, "Delete All Custom Commands",
                                          "Delete all custom commands?") == QtWidgets.QMessageBox.Yes:
            self.settings.custom_commands.clear()
            self._changed()
