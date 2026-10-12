import sys
import time
import ctypes
from PySide6 import QtCore, QtGui, QtWidgets

class FastOverlayWidget(QtWidgets.QWidget):
    def __init__(self, labels):
        super().__init__()
        self.labels = labels
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
        
        # Pre-render badge pixmaps for numbers 1..200
        self.badge_cache = {}
        self.pre_render_badges()
        self.paint_times = []

    def pre_render_badges(self):
        font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        badge_bg = QtGui.QColor(24, 119, 242, 235)
        text_color = QtGui.QColor(255, 255, 255)
        border_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0)
        
        for i in range(1, 250):
            text = str(i)
            width = max(24, 12 + len(text) * 8)
            height = 18
            pix = QtGui.QPixmap(width, height)
            pix.fill(QtCore.Qt.transparent)
            p = QtGui.QPainter(pix)
            p.setRenderHint(QtGui.QPainter.Antialiasing)
            p.setFont(font)
            p.setPen(border_pen)
            p.setBrush(badge_bg)
            p.drawRoundedRect(0, 0, width - 1, height - 1, 3, 3)
            p.setPen(text_color)
            p.drawText(0, 0, width, height, QtCore.Qt.AlignCenter, text)
            p.end()
            self.badge_cache[text] = pix

    def paintEvent(self, event):
        t0 = time.perf_counter()
        painter = QtGui.QPainter(self)
        for x, y, text in self.labels:
            pix = self.badge_cache.get(text)
            if pix:
                painter.drawPixmap(x, y, pix)
        t1 = time.perf_counter()
        self.paint_times.append((t1 - t0) * 1000)

def test_fast_overlay():
    app = QtWidgets.QApplication(sys.argv)
    labels = []
    for i in range(1, 201):
        x = (i % 20) * 90 + 20
        y = (i // 20) * 90 + 50
        labels.append((x, y, str(i)))
        
    w = FastOverlayWidget(labels)
    w.show()
    app.processEvents()
    
    for _ in range(10):
        w.update()
        app.processEvents()
        
    avg_paint = sum(w.paint_times) / len(w.paint_times)
    min_paint = min(w.paint_times)
    max_paint = max(w.paint_times)
    print(f"Cached 200-Label Paint Latency: Avg={avg_paint:.2f} ms, Min={min_paint:.2f} ms, Max={max_paint:.2f} ms")
    print(f"Budget (< 16 ms) met: {avg_paint < 16.0}")
    w.close()

if __name__ == "__main__":
    test_fast_overlay()
