"""
VoxPilot UI Automation Element Provider Implementation
Owned by: UIA-Engineer
Implements: IElementProvider
"""

import ctypes
import hashlib
import threading
import time
from typing import Optional, List, Dict, Tuple
import comtypes
import uiautomation as auto

from voxpilot.contracts.dto import LabeledElement, ScreenRect, ActionType
from voxpilot.contracts.errors import ElementNotFoundError

user32 = ctypes.windll.user32
WM_GETOBJECT = 0x003D
OBJID_CLIENT = 0xFFFFFFFC

ACTIONABLE_CONTROL_TYPES = {
    auto.ControlType.ButtonControl: [ActionType.CLICK],
    auto.ControlType.MenuItemControl: [ActionType.CLICK],
    auto.ControlType.HyperlinkControl: [ActionType.CLICK],
    auto.ControlType.EditControl: [ActionType.CLICK, ActionType.FOCUS, ActionType.TYPE],
    auto.ControlType.TabItemControl: [ActionType.CLICK, ActionType.SELECT],
    auto.ControlType.CheckBoxControl: [ActionType.CLICK],
    auto.ControlType.RadioButtonControl: [ActionType.CLICK, ActionType.SELECT],
    auto.ControlType.ComboBoxControl: [ActionType.CLICK, ActionType.EXPAND],
    auto.ControlType.SplitButtonControl: [ActionType.CLICK],
    auto.ControlType.ListItemControl: [ActionType.CLICK, ActionType.SELECT],
}

class UiaElementProvider:
    """High-speed UI Automation provider with Chromium auto-activation, occlusion, and caching."""

    def __init__(self) -> None:
        self._cached_elements: List[LabeledElement] = []
        self._cached_hwnd: int = 0
        self._cache_timestamp: float = 0.0

    def _ensure_desktop_attached(self) -> None:
        try:
            h_def = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if h_def:
                user32.SetThreadDesktop(h_def)
        except Exception:
            pass

    def _find_active_target_window(self) -> int:
        self._ensure_desktop_attached()
        fg = user32.GetForegroundWindow()
        if fg and user32.IsWindowVisible(fg):
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(fg, title_buf, 256)
            if title_buf.value and title_buf.value != "Task Switching":
                return fg

        candidates = []
        def enum_cb(h, l):
            if user32.IsWindowVisible(h):
                title_buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(h, title_buf, 256)
                t = title_buf.value
                if t and t not in ("Task Switching", "Program Manager", "Settings"):
                    candidates.append(h)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return candidates[0] if candidates else fg

    def activate_chromium_accessibility(self, hwnd: int) -> bool:
        self._ensure_desktop_attached()
        render_hwnds = []
        def enum_child(child_hwnd, lparam):
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(child_hwnd, cls_buf, 256)
            if "Chrome_RenderWidgetHostHWND" in cls_buf.value or "Intermediate D3D Window" in cls_buf.value:
                render_hwnds.append(child_hwnd)
            return True

        WNDENUMCHILD = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumChildWindows(hwnd, WNDENUMCHILD(enum_child), 0)
        
        activated = False
        for rh in render_hwnds:
            res = user32.SendMessageW(rh, WM_GETOBJECT, 0, OBJID_CLIENT)
            if res != 0:
                activated = True
        return activated

    def _discover_worker(
        self, window_handle: Optional[int], max_depth: int, timeout_ms: int, out_list: List[LabeledElement]
    ) -> None:
        self._ensure_desktop_attached()
        comtypes.CoInitialize()
        try:
            target_hwnd = window_handle or self._find_active_target_window()
            if not target_hwnd or not user32.IsWindow(target_hwnd):
                return

            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(target_hwnd, cls_buf, 256)
            if "Chrome_WidgetWin" in cls_buf.value:
                self.activate_chromium_accessibility(target_hwnd)
                time.sleep(0.05)

            root_ctrl = auto.ControlFromHandle(target_hwnd)
            if not root_ctrl:
                return

            elem_id = 1
            t_start = time.perf_counter()

            for ctrl, depth in auto.WalkControl(root_ctrl, maxDepth=max_depth):
                if (time.perf_counter() - t_start) * 1000 > timeout_ms:
                    break

                ctype = ctrl.ControlType
                if ctype in ACTIONABLE_CONTROL_TYPES or (ctrl.Name and ctype != auto.ControlType.PaneControl):
                    bbox = ctrl.BoundingRectangle
                    width = bbox.width()
                    height = bbox.height()
                    if width <= 0 or height <= 0:
                        continue

                    if ctrl.IsOffscreen:
                        continue

                    rect = ScreenRect(x=bbox.left, y=bbox.top, width=width, height=height)
                    name = (ctrl.Name or "").strip()
                    actions = ACTIONABLE_CONTROL_TYPES.get(ctype, [ActionType.CLICK])

                    key_source = f"{ctrl.GetRuntimeId()}_{ctrl.AutomationId}_{ctrl.ControlTypeName}_{name}"
                    stability_key = hashlib.md5(key_source.encode("utf-8")).hexdigest()[:12]

                    is_password = False
                    try:
                        is_password = getattr(ctrl, "IsPassword", False)
                    except Exception:
                        pass

                    labeled = LabeledElement(
                        element_id=elem_id,
                        name=name,
                        control_type=ctrl.ControlTypeName,
                        rect=rect,
                        window_handle=target_hwnd,
                        runtime_id=str(ctrl.GetRuntimeId()),
                        stability_key=stability_key,
                        is_password=is_password,
                        supported_actions=actions,
                        class_name=ctrl.ClassName,
                        automation_id=ctrl.AutomationId,
                    )
                    out_list.append(labeled)
                    elem_id += 1

            self._cached_hwnd = target_hwnd
            self._cache_timestamp = time.time()

        finally:
            comtypes.CoUninitialize()

    def discover_elements(
        self, window_handle: Optional[int] = None, max_depth: int = 8, timeout_ms: int = 800
    ) -> List[LabeledElement]:
        """Enumerate interactive controls in dedicated worker thread bound to WinSta0\\Default."""
        elements: List[LabeledElement] = []
        thread = threading.Thread(
            target=self._discover_worker,
            args=(window_handle, max_depth, timeout_ms, elements),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=max(timeout_ms / 1000.0 + 1.0, 2.0))

        self._cached_elements = elements
        return elements

    def get_element_by_id(self, element_id: int) -> Optional[LabeledElement]:
        for el in self._cached_elements:
            if el.element_id == element_id:
                return el
        return None

    def get_element_by_name(self, name: str, fuzzy: bool = True) -> Optional[LabeledElement]:
        target = name.lower().strip()
        for el in self._cached_elements:
            if (el.name or "").lower().strip() == target:
                return el
        if fuzzy:
            for el in self._cached_elements:
                if target in (el.name or "").lower():
                    return el
        return None

    def get_all_cached_elements(self) -> List[LabeledElement]:
        return list(self._cached_elements)

    def invalidate_cache(self) -> None:
        self._cached_elements.clear()
        self._cached_hwnd = 0
