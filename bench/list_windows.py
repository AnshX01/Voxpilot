import win32gui

def enum_handler(hwnd, results):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
            results.append((hwnd, title))

windows = []
win32gui.EnumWindows(enum_handler, windows)
for hwnd, title in windows[:30]:
    print(f"HWND: {hwnd} | Title: {title}")
