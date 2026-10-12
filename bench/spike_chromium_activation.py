import ctypes
import threading
import time
import comtypes
import uiautomation as auto

user32 = ctypes.windll.user32
WM_GETOBJECT = 0x003D
OBJID_CLIENT = 0xFFFFFFFC

def activate_chromium_uia(hwnd):
    # Find Chrome_RenderWidgetHostHWND
    render_hwnds = []
    def enum_child(child_hwnd, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child_hwnd, cls_buf, 256)
        if "Chrome_RenderWidgetHostHWND" in cls_buf.value or "Intermediate D3D Window" in cls_buf.value:
            render_hwnds.append(child_hwnd)
        return True
    
    WNDENUMCHILD = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumChildWindows(hwnd, WNDENUMCHILD(enum_child), 0)
    print(f"Found render host hwnds: {render_hwnds}")
    for rh in render_hwnds:
        # Send WM_GETOBJECT
        res = user32.SendMessageW(rh, WM_GETOBJECT, 0, OBJID_CLIENT)
        print(f"Sent WM_GETOBJECT to {rh}: return={res}")

def spike():
    h_def = user32.OpenDesktopW("default", 0, False, 0x1FF)
    user32.SetThreadDesktop(h_def)
    comtypes.CoInitialize()

    fg = user32.GetForegroundWindow()
    activate_chromium_uia(fg)
    time.sleep(0.5)

    ctrl = auto.ControlFromHandle(fg)
    t0 = time.perf_counter()
    count = 0
    for c, depth in auto.WalkControl(ctrl, maxDepth=10):
        count += 1
    t1 = time.perf_counter()
    print(f"After activation: Walked {count} controls in {(t1-t0)*1000:.2f} ms")

    comtypes.CoUninitialize()

t = threading.Thread(target=spike)
t.start()
t.join()
