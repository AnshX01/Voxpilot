"""VoxPilot Context & Foreground Window Service.

Inspects active foreground window handle, process credentials, caret/focus bounds,
password field state, secure desktop status, and multi-monitor geometry.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import threading
import time
from typing import Callable, Optional

from ..contracts.dto import DisplayInfo, FocusState, ScreenRect
from ..contracts.interfaces import IContextService

logger = logging.getLogger("voxpilot.automation.context_service")

# Win32 Constants
GWL_STYLE = -16
ES_PASSWORD = 0x0020
DESKTOP_READOBJECTS = 0x0001
UOI_NAME = 2
CCHDEVICENAME = 32

user32 = ctypes.windll.user32
shcore = getattr(ctypes.windll, "shcore", None)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", RECT),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * CCHDEVICENAME),
    ]


# Setup Win32 prototypes
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL

user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.CloseDesktop.restype = wintypes.BOOL
user32.GetUserObjectInformationW.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
user32.GetUserObjectInformationW.restype = wintypes.BOOL


class ContextService(IContextService):
    """Production Win32/UIA implementation of IContextService."""

    def __init__(self) -> None:
        self._focus_subscribers: list[Callable[[FocusState], None]] = []
        self._subscriber_lock = threading.Lock()
        self._last_focus_state: Optional[FocusState] = None

    def get_foreground_window(self) -> int:
        """Return HWND handle of active foreground top-level window."""
        try:
            hwnd = int(user32.GetForegroundWindow())
            return hwnd
        except Exception as exc:
            logger.debug("Failed to get foreground window: %s", exc)
            return 0

    def get_focus_state(self) -> FocusState:
        """Inspect and return current focus target and security state."""
        hwnd = self.get_foreground_window()
        if not hwnd:
            return FocusState(
                hwnd=0,
                process_id=0,
                process_name="",
                window_title="",
                class_name="",
                is_password=False,
                is_elevated=False,
            )

        # Process ID
        pid = wintypes.DWORD()
        thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_id = int(pid.value)

        # Title
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        window_title = title_buf.value

        # Class Name
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value

        # Window Rect
        rc = RECT()
        focused_rect: Optional[ScreenRect] = None
        if user32.GetWindowRect(hwnd, ctypes.byref(rc)):
            focused_rect = ScreenRect(
                x=rc.left,
                y=rc.top,
                width=rc.right - rc.left,
                height=rc.bottom - rc.top,
            )

        # Caret and Child Focus Inspection
        caret_rect: Optional[ScreenRect] = None
        focused_hwnd = hwnd
        is_password = False

        if thread_id:
            gui_info = GUITHREADINFO()
            gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
            if user32.GetGUIThreadInfo(thread_id, ctypes.byref(gui_info)):
                if gui_info.hwndFocus:
                    focused_hwnd = int(gui_info.hwndFocus)
                if gui_info.hwndCaret:
                    caret_rect = ScreenRect(
                        x=gui_info.rcCaret.left,
                        y=gui_info.rcCaret.top,
                        width=gui_info.rcCaret.right - gui_info.rcCaret.left,
                        height=gui_info.rcCaret.bottom - gui_info.rcCaret.top,
                    )

        # Password inspection on focused HWND or main HWND
        is_password = self._check_is_password(focused_hwnd)

        # Process Name
        process_name = self._get_process_name_by_pid(process_id)

        focus_state = FocusState(
            hwnd=hwnd,
            process_id=process_id,
            process_name=process_name,
            window_title=window_title,
            class_name=class_name,
            is_password=is_password,
            is_elevated=False,
            focused_rect=focused_rect,
            caret_rect=caret_rect,
        )
        self._last_focus_state = focus_state
        return focus_state

    def is_password_focused(self) -> bool:
        """Check if active focus is currently on a secure password field."""
        state = self.get_focus_state()
        return state.is_password

    def is_secure_desktop(self) -> bool:
        """Check if the active desktop station is a Secure Desktop (UAC / Lock)."""
        h_desk = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
        if not h_desk:
            # If OpenInputDesktop fails with error 5 (ACCESS_DENIED),
            # it indicates a protected/secure desktop like UAC consent or Winlogon.
            last_err = ctypes.GetLastError()
            if last_err in (5, 0x05):
                return True
            return False

        try:
            needed = wintypes.DWORD()
            name_buf = ctypes.create_unicode_buffer(256)
            success = user32.GetUserObjectInformationW(
                h_desk,
                UOI_NAME,
                name_buf,
                ctypes.sizeof(name_buf),
                ctypes.byref(needed),
            )
            if success:
                desk_name = name_buf.value.lower()
                # Default interactive desktop is "default"
                if desk_name != "default":
                    return True
            return False
        finally:
            user32.CloseDesktop(h_desk)

    def get_displays(self) -> list[DisplayInfo]:
        """Return display geometry and DPI scaling for all connected monitors."""
        displays: list[DisplayInfo] = []

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )

        def _enum_proc(h_mon: wintypes.HMONITOR, hdc: wintypes.HDC, lprc: Any, lparam: Any) -> bool:
            mi = MONITORINFOEXW()
            mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(h_mon, ctypes.byref(mi)):
                bounds = ScreenRect(
                    x=mi.rcMonitor.left,
                    y=mi.rcMonitor.top,
                    width=mi.rcMonitor.right - mi.rcMonitor.left,
                    height=mi.rcMonitor.bottom - mi.rcMonitor.top,
                )
                work = ScreenRect(
                    x=mi.rcWork.left,
                    y=mi.rcWork.top,
                    width=mi.rcWork.right - mi.rcWork.left,
                    height=mi.rcWork.bottom - mi.rcWork.top,
                )
                is_primary = bool(mi.dwFlags & 1)  # MONITORINFOF_PRIMARY
                dev_name = str(mi.szDevice)

                # Query per-monitor DPI if shcore is available
                scale = 1.0
                if shcore and hasattr(shcore, "GetDpiForMonitor"):
                    dpi_x = wintypes.UINT()
                    dpi_y = wintypes.UINT()
                    # MDT_EFFECTIVE_DPI = 0
                    if shcore.GetDpiForMonitor(h_mon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                        scale = round(float(dpi_x.value) / 96.0, 2)

                displays.append(
                    DisplayInfo(
                        display_id=dev_name or f"display_{len(displays)}",
                        bounds=bounds,
                        work_area=work,
                        scale_factor=scale,
                        is_primary=is_primary,
                        device_name=dev_name,
                    )
                )
            return True

        proc = MonitorEnumProc(_enum_proc)
        user32.EnumDisplayMonitors(None, None, proc, 0)

        if not displays:
            # Fallback single monitor query
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            displays.append(
                DisplayInfo(
                    display_id="primary",
                    bounds=ScreenRect(0, 0, w, h),
                    work_area=ScreenRect(0, 0, w, h),
                    scale_factor=1.0,
                    is_primary=True,
                    device_name="PrimaryDisplay",
                )
            )

        return displays

    def subscribe_focus_changed(self, callback: Callable[[FocusState], None]) -> None:
        """Register hook for foreground window or keyboard focus change events."""
        with self._subscriber_lock:
            if callback not in self._focus_subscribers:
                self._focus_subscribers.append(callback)

    def unsubscribe_focus_changed(self, callback: Callable[[FocusState], None]) -> None:
        """Unregister focus change event listener."""
        with self._subscriber_lock:
            if callback in self._focus_subscribers:
                self._focus_subscribers.remove(callback)

    def _check_is_password(self, hwnd: int) -> bool:
        """Check if target control has password style or class."""
        if not hwnd:
            return False
        try:
            # Check Win32 Edit control ES_PASSWORD style
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            if (style & ES_PASSWORD) == ES_PASSWORD:
                return True

            # Check class name heuristics
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            cname = class_buf.value.lower()
            if "password" in cname:
                return True

            return False
        except Exception:
            return False

    def _get_process_name_by_pid(self, pid: int) -> str:
        """Query executable base name for given process ID."""
        if pid <= 0:
            return ""
        try:
            # Use kernel32 QueryFullProcessImageNameW
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(1024)
                    if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                        return os.path.basename(buf.value)
                finally:
                    kernel32.CloseHandle(h_proc)
        except Exception:
            pass
        return ""
