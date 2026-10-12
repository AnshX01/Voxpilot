import ctypes
import subprocess
import threading
import time
import comtypes
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL = 0x1FF

def spike_target():
    h_def = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
    user32.SetThreadDesktop(h_def)
    comtypes.CoInitialize()

    # Launch Notepad if not already running
    p = subprocess.Popen(["notepad.exe"])
    time.sleep(1.0)

    notepad_elem = auto.WindowControl(searchDepth=1, ClassName="Notepad")
    if not notepad_elem.Exists(3, 1):
        # Try modern Windows 11 Notepad
        notepad_elem = auto.WindowControl(searchDepth=2, SubName="Notepad")
    
    print(f"Notepad found: {notepad_elem.Name} (HWND: {notepad_elem.NativeWindowHandle})")
    
    t0 = time.perf_counter()
    # Find all interactive elements
    interactive_types = {
        auto.ControlType.ButtonControl,
        auto.ControlType.MenuItemControl,
        auto.ControlType.TabItemControl,
        auto.ControlType.EditControl,
        auto.ControlType.CheckBoxControl,
        auto.ControlType.RadioButtonControl,
        auto.ControlType.ComboBoxControl,
        auto.ControlType.HyperlinkControl,
        auto.ControlType.SplitButtonControl
    }
    
    elements = []
    for c, depth in auto.WalkControl(notepad_elem, maxDepth=8):
        if c.ControlType in interactive_types:
            rect = c.BoundingRectangle
            if rect.width() > 0 and rect.height() > 0:
                elements.append((c.Name or "<unnamed>", c.ControlTypeName, (rect.left, rect.top, rect.right, rect.bottom)))
    
    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000
    print(f"Enumerated {len(elements)} actionable elements in {duration_ms:.2f} ms")
    for idx, (name, ctype, bbox) in enumerate(elements[:15], 1):
        print(f"  [{idx:02d}] {name:20s} | {ctype:15s} | BBox: {bbox}")

    comtypes.CoUninitialize()

t = threading.Thread(target=spike_target)
t.start()
t.join()
