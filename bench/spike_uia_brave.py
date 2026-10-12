import ctypes
import threading
import time
import comtypes
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL = 0x1FF

def spike_brave():
    h_def = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
    user32.SetThreadDesktop(h_def)
    comtypes.CoInitialize()

    fg = user32.GetForegroundWindow()
    title_buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(fg, title_buf, 256)
    print(f"Foreground Window HWND: {fg}, Title: '{title_buf.value}'")

    ctrl = auto.ControlFromHandle(fg)
    print(f"Root control: {ctrl.Name} ({ctrl.ControlTypeName})")

    t0 = time.perf_counter()
    elements = []
    # Walk tree up to depth 6
    for c, depth in auto.WalkControl(ctrl, maxDepth=6):
        rect = c.BoundingRectangle
        if rect.width() > 0 and rect.height() > 0:
            name = c.Name
            ctype = c.ControlTypeName
            elements.append((name, ctype, depth, (rect.left, rect.top, rect.right, rect.bottom)))

    t1 = time.perf_counter()
    print(f"Enumerated {len(elements)} elements across depth 6 in {(t1-t0)*1000:.2f} ms")
    
    # Filter for actionable/interactive
    actionable_types = {
        'ButtonControl', 'HyperlinkControl', 'MenuItemControl', 'EditControl', 
        'TabItemControl', 'CheckBoxControl', 'RadioButtonControl', 'ComboBoxControl'
    }
    actionable = [e for e in elements if e[1] in actionable_types or e[0]]
    print(f"Actionable candidates count: {len(actionable)}")
    for idx, (name, ctype, depth, bbox) in enumerate(actionable[:20], 1):
        print(f"  [{idx:02d}] (d={depth}) {name[:30]:30s} | {ctype:20s} | {bbox}")

    comtypes.CoUninitialize()

t = threading.Thread(target=spike_brave)
t.start()
t.join()
