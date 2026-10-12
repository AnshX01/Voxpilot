import ctypes
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GENERIC_ALL = 0x10000000
DESKTOP_SWITCHDESKTOP = 0x0100
DESKTOP_READOBJECTS = 0x0001
DESKTOP_WRITEOBJECTS = 0x0002
DESKTOP_ENUMERATE = 0x0040

# Try OpenInputDesktop
h_input = user32.OpenInputDesktop(0, False, GENERIC_ALL)
err = kernel32.GetLastError()
print(f"OpenInputDesktop: {h_input}, LastError: {err}")

# Try OpenDesktopW "default"
h_def = user32.OpenDesktopW("default", 0, False, GENERIC_ALL)
err2 = kernel32.GetLastError()
print(f"OpenDesktopW default: {h_def}, LastError: {err2}")

if h_def:
    ret = user32.SetThreadDesktop(h_def)
    print("SetThreadDesktop ret:", ret)
    hwnds = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, lparam):
        title_buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title_buf, 256)
        if title_buf.value:
            hwnds.append((hwnd, title_buf.value))
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    print("Default desktop visible windows count:", len(hwnds))
    for h, t in hwnds[:15]:
        print(f"  [{h}] {t}")
