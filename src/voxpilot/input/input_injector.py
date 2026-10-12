"""
VoxPilot Windows Input Injector Implementation
Owned by: Input-Engineer
Implements: IInputInjector
"""

import ctypes
import time
from typing import Tuple, List, Optional
from voxpilot.contracts.dto import MouseButton, ScrollDirection
from voxpilot.contracts.errors import InputInjectionError

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

ULONG_PTR = ctypes.c_ulonglong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

VK_MAP = {
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "backspace": 0x08,
    "tab": 0x09,
    "space": 0x20,
    "delete": 0x2E,
    "del": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}

MODIFIER_VKS = [0x10, 0x11, 0x12, 0x5B, 0x5C]

class WindowsInputInjector:
    """Hardware-level SendInput injector with multi-monitor coordinate normalization."""

    def __init__(self) -> None:
        self._ensure_desktop_attached()

    def _ensure_desktop_attached(self) -> None:
        try:
            h_def = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if h_def:
                user32.SetThreadDesktop(h_def)
        except Exception:
            pass

    def _to_normalized_coords(self, x: int, y: int) -> Tuple[int, int]:
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = max(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN), 1)
        vh = max(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN), 1)

        norm_x = int((x - vx) * 65535 / (vw - 1))
        norm_y = int((y - vy) * 65535 / (vh - 1))
        return norm_x, norm_y

    def get_cursor_position(self) -> Tuple[int, int]:
        self._ensure_desktop_attached()
        pt = POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            return pt.x, pt.y
        return 0, 0

    def move_cursor(self, x: int, y: int, smooth: bool = False, duration_ms: int = 100) -> None:
        self._ensure_desktop_attached()
        if smooth and duration_ms > 0:
            start_x, start_y = self.get_cursor_position()
            steps = max(int(duration_ms / 10), 5)
            for i in range(1, steps + 1):
                cur_x = int(start_x + (x - start_x) * (i / steps))
                cur_y = int(start_y + (y - start_y) * (i / steps))
                norm_x, norm_y = self._to_normalized_coords(cur_x, cur_y)
                inp = INPUT(type=INPUT_MOUSE)
                inp.u.mi.dx = norm_x
                inp.u.mi.dy = norm_y
                inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                time.sleep(duration_ms / (1000 * steps))
        else:
            norm_x, norm_y = self._to_normalized_coords(x, y)
            inp = INPUT(type=INPUT_MOUSE)
            inp.u.mi.dx = norm_x
            inp.u.mi.dy = norm_y
            inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def mouse_down(self, button: MouseButton = MouseButton.LEFT) -> None:
        self._ensure_desktop_attached()
        flag = MOUSEEVENTF_LEFTDOWN
        if button == MouseButton.RIGHT:
            flag = MOUSEEVENTF_RIGHTDOWN
        elif button == MouseButton.MIDDLE:
            flag = MOUSEEVENTF_MIDDLEDOWN
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dwFlags = flag
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def mouse_up(self, button: MouseButton = MouseButton.LEFT) -> None:
        self._ensure_desktop_attached()
        flag = MOUSEEVENTF_LEFTUP
        if button == MouseButton.RIGHT:
            flag = MOUSEEVENTF_RIGHTUP
        elif button == MouseButton.MIDDLE:
            flag = MOUSEEVENTF_MIDDLEUP
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dwFlags = flag
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def click(self, button: MouseButton = MouseButton.LEFT, count: int = 1) -> None:
        for i in range(count):
            self.mouse_down(button)
            time.sleep(0.02)
            self.mouse_up(button)
            if i < count - 1:
                time.sleep(0.05)

    def click_at(
        self,
        x: int,
        y: int,
        button: MouseButton = MouseButton.LEFT,
        count: int = 1,
        restore_cursor: bool = False,
    ) -> None:
        orig_x, orig_y = self.get_cursor_position() if restore_cursor else (0, 0)
        self.move_cursor(x, y)
        time.sleep(0.02)
        self.click(button, count)
        if restore_cursor:
            time.sleep(0.02)
            self.move_cursor(orig_x, orig_y)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: MouseButton = MouseButton.LEFT,
        duration_ms: int = 300,
    ) -> None:
        self.move_cursor(start_x, start_y)
        time.sleep(0.03)
        self.mouse_down(button)
        time.sleep(0.03)
        self.move_cursor(end_x, end_y, smooth=True, duration_ms=duration_ms)
        time.sleep(0.03)
        self.mouse_up(button)

    def scroll(
        self,
        direction: ScrollDirection = ScrollDirection.DOWN,
        amount: int = 120,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> None:
        self._ensure_desktop_attached()
        if x is not None and y is not None:
            self.move_cursor(x, y)
            time.sleep(0.02)

        flag = MOUSEEVENTF_WHEEL
        delta = amount
        if direction == ScrollDirection.DOWN:
            delta = -amount
        elif direction == ScrollDirection.UP:
            delta = amount
        elif direction == ScrollDirection.RIGHT:
            flag = MOUSEEVENTF_HWHEEL
            delta = amount
        elif direction == ScrollDirection.LEFT:
            flag = MOUSEEVENTF_HWHEEL
            delta = -amount

        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dwFlags = flag
        inp.u.mi.mouseData = delta & 0xFFFFFFFF
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def key_down(self, key: str) -> None:
        self._ensure_desktop_attached()
        vk = self._resolve_vk(key)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki.wVk = vk
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def key_up(self, key: str) -> None:
        self._ensure_desktop_attached()
        vk = self._resolve_vk(key)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def send_key(self, key: str, modifiers: Optional[List[str]] = None) -> None:
        """Press key with modifiers, with strict guarantee of modifier release on exception."""
        self._ensure_desktop_attached()
        mods = modifiers or []
        try:
            for m in mods:
                self.key_down(m)
            time.sleep(0.01)

            self.key_down(key)
            time.sleep(0.01)
            self.key_up(key)
        finally:
            for m in reversed(mods):
                try:
                    self.key_up(m)
                except Exception:
                    pass

    def send_text(self, text: str) -> None:
        self._ensure_desktop_attached()
        for char in text:
            code = ord(char)
            inp_down = INPUT(type=INPUT_KEYBOARD)
            inp_down.u.ki.wVk = 0
            inp_down.u.ki.wScan = code
            inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE

            inp_up = INPUT(type=INPUT_KEYBOARD)
            inp_up.u.ki.wVk = 0
            inp_up.u.ki.wScan = code
            inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

            inputs = (INPUT * 2)(inp_down, inp_up)
            user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
            time.sleep(0.005)

    def release_all_modifiers(self) -> None:
        self._ensure_desktop_attached()
        for vk in MODIFIER_VKS:
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.u.ki.wVk = vk
            inp.u.ki.dwFlags = KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _resolve_vk(self, key: str) -> int:
        k = key.lower().strip()
        if k in VK_MAP:
            return VK_MAP[k]
        if len(k) == 1:
            return user32.VkKeyScanW(ord(k)) & 0xFF
        raise InputInjectionError(f"Unsupported key identifier: {key}")
