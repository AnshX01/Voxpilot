import ctypes
import time

user32 = ctypes.windll.user32

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
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

def send_mouse_move(x, y):
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    
    # Normalize to 0..65535 across virtual desktop
    norm_x = int((x - vx) * 65535 / (vw - 1))
    norm_y = int((y - vy) * 65535 / (vh - 1))
    
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = norm_x
    inp.u.mi.dy = norm_y
    inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def test_input():
    pt_orig = POINT()
    user32.GetCursorPos(ctypes.byref(pt_orig))
    print(f"Original Cursor Position: ({pt_orig.x}, {pt_orig.y})")
    
    # Test move to (500, 400)
    send_mouse_move(500, 400)
    time.sleep(0.05)
    pt_new = POINT()
    user32.GetCursorPos(ctypes.byref(pt_new))
    print(f"Moved Cursor Position: ({pt_new.x}, {pt_new.y})")
    
    # Restore original cursor
    send_mouse_move(pt_orig.x, pt_orig.y)
    
    success = (abs(pt_new.x - 500) <= 2 and abs(pt_new.y - 400) <= 2)
    print(f"Cursor Precision Test Passed: {success}")

if __name__ == "__main__":
    test_input()
