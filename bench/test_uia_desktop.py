import ctypes
import threading
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL = 0x1FF

def uia_worker():
    h_def = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
    if not h_def:
        print("Failed OpenDesktopW")
        return
    res = user32.SetThreadDesktop(h_def)
    if not res:
        print("Failed SetThreadDesktop")
        return
    
    # Initialize COM on this thread
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()

    import uiautomation as auto
    
    # Get foreground window on default desktop
    fg = user32.GetForegroundWindow()
    title_buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(fg, title_buf, 256)
    print(f"Foreground Window: [{fg}] '{title_buf.value}'")
    
    # Now find the element for foreground window or root desktop
    t0 = time.perf_counter()
    fg_elem = auto.ControlFromHandle(fg)
    print(f"ControlFromHandle: {fg_elem.Name} ({fg_elem.ControlTypeName})")
    
    # Enumerate interactive children
    children = fg_elem.GetChildren()
    t1 = time.perf_counter()
    print(f"Found {len(children)} top-level children in {(t1-t0)*1000:.2f} ms")
    
    count = 0
    for c in children:
        count += 1
        rect = c.BoundingRectangle
        print(f"  [{count}] {c.Name or '<unnamed>'} | {c.ControlTypeName} | Rect: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
    
    comtypes.CoUninitialize()

t = threading.Thread(target=uia_worker)
t.start()
t.join()
