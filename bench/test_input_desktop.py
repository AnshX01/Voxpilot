import ctypes
import threading
import time

user32 = ctypes.windll.user32
DESKTOP_ALL = 0x1FF

# Win32 SendInput Structures
ULONG_PTR = ctypes.c_ulonglong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort)
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION)
    ]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def input_worker():
    h_def = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
    user32.SetThreadDesktop(h_def)
    
    pt_orig = POINT()
    user32.GetCursorPos(ctypes.byref(pt_orig))
    print(f"[Default Desktop] Current Cursor Position: ({pt_orig.x}, {pt_orig.y})")
    
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print(f"Virtual Screen: ({vx}, {vy}, {vw}, {vh})")
    
    target_x, target_y = 640, 480
    norm_x = int((target_x - vx) * 65535 / (vw - 1))
    norm_y = int((target_y - vy) * 65535 / (vh - 1))
    
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = norm_x
    inp.u.mi.dy = norm_y
    inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    
    ret = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    print(f"SendInput return: {ret}")
    time.sleep(0.05)
    
    pt_new = POINT()
    user32.GetCursorPos(ctypes.byref(pt_new))
    print(f"New Cursor Position: ({pt_new.x}, {pt_new.y})")
    
    # Also test SetCursorPos
    user32.SetCursorPos(target_x, target_y)
    user32.GetCursorPos(ctypes.byref(pt_new))
    print(f"After SetCursorPos: ({pt_new.x}, {pt_new.y})")

t = threading.Thread(target=input_worker)
t.start()
t.join()
