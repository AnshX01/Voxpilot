import ctypes

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
hwnds = []

def cb(hwnd, lparam):
    hwnds.append(hwnd)
    return True

proc = WNDENUMPROC(cb)
res = user32.EnumWindows(proc, 0)
print("EnumWindows return:", res, "Count:", len(hwnds))

# Let's inspect thread desktop name
hdesk = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
name_buf = ctypes.create_unicode_buffer(256)
needed = ctypes.c_ulong()
user32.GetUserObjectInformationW(hdesk, 2, name_buf, ctypes.sizeof(name_buf), ctypes.byref(needed))
print("Desktop Name:", name_buf.value)

# Also check GetDesktopWindow
desk_hwnd = user32.GetDesktopWindow()
print("GetDesktopWindow:", desk_hwnd)

# Also test uiautomation root element
import uiautomation as auto
root = auto.GetRootControl()
print("UIAutomation Root:", root.Name, root.ControlType)
children = root.GetChildren()
print("Root direct children count:", len(children))
for c in children[:10]:
    print(" - Child:", c.Name, "| ControlType:", c.ControlTypeName, "| ClassName:", c.ClassName)
