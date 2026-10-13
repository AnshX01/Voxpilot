"""Voice Control Commands window and interactive tutorial (Qt)."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

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
    """Small floating "Commands" palette like the guide: grey title, collapsible category,
    one column of phrases with alternating rows. It never takes keyboard focus, so the app
    you are dictating into stays active."""

    def __init__(self, engine=None, parent=None, rows=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Commands")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setFocusPolicy(QtCore.Qt.NoFocus)
        self.tree.setIndentation(10)
        self.tree.setFrameShape(QtWidgets.QFrame.NoFrame)
        font = self.tree.font()
        font.setPointSizeF(9.0)
        self.tree.setFont(font)
        self.tree.setStyleSheet(
            "QTreeWidget { background: #f4f2f0; alternate-background-color: #e9e6e3; color: #1d1d1f; }"
            "QTreeWidget::item { padding: 1px 4px; }"
        )
        lay.addWidget(self.tree)
        if rows is None:
            ctx = "general"
            if engine is not None and engine.mode.value in ("dictation", "spelling", "swift"):
                ctx = "text"
            rows = commands_for_context(ctx)
        cats = {}
        for cat, phrase, desc in rows:
            top = cats.get(cat)
            if top is None:
                top = QtWidgets.QTreeWidgetItem([cat])
                f = top.font(0)
                f.setBold(True)
                top.setFont(0, f)
                top.setForeground(0, QtGui.QBrush(QtGui.QColor(110, 106, 102)))
                self.tree.addTopLevelItem(top)
                cats[cat] = top
            child = QtWidgets.QTreeWidgetItem([phrase])
            child.setToolTip(0, desc)
            top.addChild(child)
        self.tree.expandItem(self.tree.topLevelItem(0))
        self.tree.setTextElideMode(QtCore.Qt.ElideNone)
        self._fit_to_content()

    def _fit_to_content(self) -> None:
        """Bounded palette: wide enough for the longest phrase, tall enough for the open rows."""
        fm = QtGui.QFontMetrics(self.tree.font())
        widest = 0
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            widest = max(widest, fm.horizontalAdvance(top.text(0)) + 30)
            for j in range(top.childCount()):
                widest = max(widest, fm.horizontalAdvance(top.child(j).text(0)) + 40)
        row_h = max(fm.height() + 6, 18)
        visible_rows = 0
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            visible_rows += 1 + (top.childCount() if top.isExpanded() else 0)
        self.resize(max(200, widest), min(520, row_h * visible_rows + 8))


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
