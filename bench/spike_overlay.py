import sys
import time
import ctypes
from PySide6 import QtCore, QtGui, QtWidgets

user32 = ctypes.windll.user32
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
GWL_EXSTYLE = -20

class OverlayWidget(QtWidgets.QWidget):
    def __init__(self, labels):
        super().__init__()
        self.labels = labels # list of (x, y, text)
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
        self.paint_times = []

    def showEvent(self, event):
        super().showEvent(event)
        # Verify Win32 style
        hwnd = int(self.winId())
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # Ensure click-through and no-activate
        new_style = ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

    def paintEvent(self, event):
        t0 = time.perf_counter()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold)
        painter.setFont(font)
        
        badge_bg = QtGui.QColor(30, 144, 255, 230) # Dodger blue
        text_color = QtGui.QColor(255, 255, 255)
        border_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 180), 1.5)
        
        for x, y, text in self.labels:
            # Draw badge pill
            rect = QtCore.QRect(x, y, 28, 20)
            painter.setPen(border_pen)
            painter.setBrush(badge_bg)
            painter.drawRoundedRect(rect, 4, 4)
            
            painter.setPen(text_color)
            painter.drawText(rect, QtCore.Qt.AlignCenter, str(text))
            
        t1 = time.perf_counter()
        self.paint_times.append((t1 - t0) * 1000)

def spike_overlay():
    app = QtWidgets.QApplication(sys.argv)
    
    # Generate 200 labels
    labels = []
    for i in range(1, 201):
        x = (i % 20) * 90 + 20
        y = (i // 20) * 90 + 50
        labels.append((x, y, str(i)))
        
    overlay = OverlayWidget(labels)
    overlay.show()
    
    # Trigger paint and verify styles
    app.processEvents()
    
    hwnd = int(overlay.winId())
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    is_transparent = bool(ex_style & WS_EX_TRANSPARENT)
    is_noactivate = bool(ex_style & WS_EX_NOACTIVATE)
    is_topmost = bool(ex_style & WS_EX_TOPMOST)
    
    print(f"Overlay HWND: {hwnd}")
    print(f"Win32 Styles: WS_EX_TRANSPARENT={is_transparent}, WS_EX_NOACTIVATE={is_noactivate}, WS_EX_TOPMOST={is_topmost}")
    
    # Repaint multiple times to get stable paint latency benchmark
    for _ in range(5):
        overlay.update()
        app.processEvents()
        
    avg_paint = sum(overlay.paint_times) / max(len(overlay.paint_times), 1)
    max_paint = max(overlay.paint_times) if overlay.paint_times else 0
    print(f"200-Label Paint Latency: Avg={avg_paint:.2f} ms, Max={max_paint:.2f} ms (Budget: < 16 ms)")
    
    # Capture screenshot of overlay to evidence
    pixmap = overlay.grab()
    pixmap.save("docs/evidence/screenshots/overlay_spike_200_labels.png")
    print("Screenshot saved to docs/evidence/screenshots/overlay_spike_200_labels.png")
    
    overlay.close()

if __name__ == "__main__":
    spike_overlay()
