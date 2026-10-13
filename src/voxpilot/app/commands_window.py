"""Voice Control Commands window and interactive tutorial (Qt)."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .command_catalog import commands_for_context

TUTORIAL_STEPS = [
    ("Say \"Show numbers\" to label what's on screen.", "SHOW_NUMBERS"),
    ("Say \"Hide numbers\" to remove the labels.", "HIDE_NUMBERS"),
    ("Say \"Show grid\" to overlay a numbered grid.", "SHOW_GRID"),
    ("Say \"Hide grid\".", "HIDE_GRID"),
    ("Say \"Scroll down\".", "SCROLL"),
    ("Say \"Stop listening\" when you want to pause.", "GO_TO_SLEEP"),
]


class CommandsWindow(QtWidgets.QWidget):
    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Voice Control Commands")
        self.resize(900, 560)
        lay = QtWidgets.QVBoxLayout(self)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Command", "What it does"])
        lay.addWidget(self.tree)
        btn = QtWidgets.QPushButton("Open Tutorial")
        btn.clicked.connect(lambda: Tutorial(engine, self).show())
        lay.addWidget(btn)
        ctx = "text" if engine.mode.value in ("dictation", "spelling", "swift") else "general"
        cats = {}
        for cat, phrase, desc in commands_for_context(ctx):
            top = cats.get(cat)
            if top is None:
                top = QtWidgets.QTreeWidgetItem([cat])
                self.tree.addTopLevelItem(top)
                cats[cat] = top
            top.addChild(QtWidgets.QTreeWidgetItem([phrase, desc]))
        self.tree.expandAll()
        self.tree.setWordWrap(True)
        self.tree.setTextElideMode(QtCore.Qt.ElideNone)
        self.tree.header().setStretchLastSection(True)
        self.tree.resizeColumnToContents(0)
        self.tree.setColumnWidth(0, max(self.tree.columnWidth(0), 330))


class Tutorial(QtWidgets.QDialog):
    """Interactive practice: advances when the engine reports the expected command."""

    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Voice Control Tutorial")
        self.engine = engine
        self.step = 0
        self.setMinimumSize(420, 140)
        self.label = QtWidgets.QLabel()
        self.label.setWordWrap(True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.label)
        self._render()
        engine.result_listeners = getattr(engine, "result_listeners", [])
        engine.result_listeners.append(self._on_result)

    def _render(self) -> None:
        if self.step >= len(TUTORIAL_STEPS):
            self.label.setText("You're done. Say \"Show commands\" any time to see what you can say.")
        else:
            self.label.setText(f"Step {self.step + 1} of {len(TUTORIAL_STEPS)}\n\n{TUTORIAL_STEPS[self.step][0]}")

    def _on_result(self, res) -> None:
        name = getattr(getattr(res, "matched_intent", None), "name", None)
        if self.step < len(TUTORIAL_STEPS) and name == TUTORIAL_STEPS[self.step][1]:
            self.step += 1
            self._render()
