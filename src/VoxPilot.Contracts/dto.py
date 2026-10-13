"""VoxPilot Core Data Transfer Objects (DTOs) and Enumerations."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ============================================================================
# Enumerations
# ============================================================================


class EngineMode(str, Enum):
    """Operational mode of the VoxPilot speech and control pipeline."""

    COMMAND = "command"
    DICTATION = "dictation"
    SLEEP = "sleep"
    PAUSED = "paused"


class CommandStatus(str, Enum):
    """Outcome status for parsed and executed voice commands."""

    SUCCESS = "success"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"
    ELEMENT_GONE = "element_gone"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    ERROR = "error"


class BlockedReason(str, Enum):
    """Specific cause for a command execution block."""

    UIPI = "uipi"  # Target window is running with higher privilege (e.g. Administrator)
    SECURE_DESKTOP = "secure_desktop"  # Windows UAC elevation prompt or lock screen active
    PASSWORD_FIELD = "password_field"  # Focus target is marked as secure password input
    REQUIRES_CONFIRMATION = "requires_confirmation"  # High-risk action awaiting user confirmation
    UAC_ELEVATION = "uac_elevation"  # System elevation challenge
    DESKTOP_SWITCH = "desktop_switch"  # Active desktop station changed away from WinSta0\Default


class OverlayMode(str, Enum):
    """Visual display mode of the hardware-accelerated non-activating canvas."""

    OFF = "off"
    NUMBERS = "numbers"
    CONTINUOUS_NUMBERS = "continuous_numbers"
    NAMES = "names"
    GRID = "grid"
    DISAMBIGUATION = "disambiguation"


class ActionType(str, Enum):
    """Supported interactive control actions."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TRIPLE_CLICK = "triple_click"
    RIGHT_CLICK = "right_click"
    MIDDLE_CLICK = "middle_click"
    LONG_PRESS = "long_press"
    DRAG = "drag"
    FOCUS = "focus"
    SELECT = "select"
    EXPAND = "expand"
    COLLAPSE = "collapse"
    SCROLL = "scroll"
    TYPE = "type"
    CUSTOM = "custom"


class MouseButton(str, Enum):
    """Synthesized mouse buttons."""

    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class ScrollDirection(str, Enum):
    """Scroll movement vectors."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


# ============================================================================
# Spatial & Display Data Models
# ============================================================================


@dataclass(frozen=True, slots=True)
class ScreenRect:
    """Represents a 2D bounding rectangle in virtual screen coordinates."""

    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        """Left edge coordinate."""
        return self.x

    @property
    def top(self) -> int:
        """Top edge coordinate."""
        return self.y

    @property
    def right(self) -> int:
        """Right edge coordinate."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge coordinate."""
        return self.y + self.height

    def center(self) -> tuple[int, int]:
        """Compute the integer center point of the rectangle."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, px: int, py: int) -> bool:
        """Check if point (px, py) lies within this rectangle."""
        return (self.left <= px < self.right) and (self.top <= py < self.bottom)

    def intersects(self, other: ScreenRect) -> bool:
        """Check if this rectangle overlaps with another rectangle."""
        return not (
            self.right <= other.left
            or self.left >= other.right
            or self.bottom <= other.top
            or self.top >= other.bottom
        )

    def intersection(self, other: ScreenRect) -> Optional[ScreenRect]:
        """Compute overlapping region between two rectangles."""
        ix1 = max(self.left, other.left)
        iy1 = max(self.top, other.top)
        ix2 = min(self.right, other.right)
        iy2 = min(self.bottom, other.bottom)
        if ix2 > ix1 and iy2 > iy1:
            return ScreenRect(x=ix1, y=iy1, width=ix2 - ix1, height=iy2 - iy1)
        return None

    def union(self, other: ScreenRect) -> ScreenRect:
        """Compute minimum bounding rectangle enclosing both rectangles."""
        ux1 = min(self.left, other.left)
        uy1 = min(self.top, other.top)
        ux2 = max(self.right, other.right)
        uy2 = max(self.bottom, other.bottom)
        return ScreenRect(x=ux1, y=uy1, width=ux2 - ux1, height=uy2 - uy1)

    def area(self) -> int:
        """Total enclosed pixel area."""
        return max(0, self.width) * max(0, self.height)

    def is_empty(self) -> bool:
        """Check if the rectangle has non-positive area."""
        return self.width <= 0 or self.height <= 0

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Export as (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)


@dataclass(slots=True)
class DisplayInfo:
    """Information regarding a physical monitor or display device."""

    display_id: str
    bounds: ScreenRect
    work_area: ScreenRect
    scale_factor: float = 1.0
    is_primary: bool = False
    device_name: str = ""


# ============================================================================
# Accessibility & UI Element Data Models
# ============================================================================


@dataclass(slots=True)
class LabeledElement:
    """Interactive control discovered via UI Automation or visual heuristics."""

    element_id: int
    name: str
    control_type: str
    rect: ScreenRect
    window_handle: int
    runtime_id: str = ""
    stability_key: str = ""
    is_keyboard_focusable: bool = True
    is_password: bool = False
    is_offscreen: bool = False
    is_focused: bool = False
    depth: int = 0
    z_index: int = 0
    supported_actions: list[ActionType] = field(default_factory=list)
    class_name: str = ""
    automation_id: str = ""
    help_text: str = ""
    value: Optional[str] = None


@dataclass(slots=True)
class FocusState:
    """Current focus and foreground target context."""

    hwnd: int
    process_id: int
    process_name: str
    window_title: str
    class_name: str
    is_password: bool = False
    is_elevated: bool = False
    focused_rect: Optional[ScreenRect] = None
    caret_rect: Optional[ScreenRect] = None


# ============================================================================
# Speech & NLU Data Models
# ============================================================================


@dataclass(slots=True)
class TranscriptWord:
    """Individual recognized word with temporal alignment."""

    word: str
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0
    confidence: float = 1.0


@dataclass(slots=True)
class TranscriptEvent:
    """Speech recognition streaming event emitted by speech engines."""

    text: str
    is_final: bool
    confidence: float = 1.0
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0
    words: list[TranscriptWord] = field(default_factory=list)
    raw_hypothesis: str = ""
    engine_mode: EngineMode = EngineMode.COMMAND


@dataclass(slots=True)
class Intent:
    """Parsed semantic intention extracted from a speech transcript."""

    name: str
    confidence: float = 1.0
    slots: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    execution_strategy: str = "default"
    requires_confirmation: bool = False


# ============================================================================
# Execution Result & Diagnostic Data Models
# ============================================================================


@dataclass(slots=True)
class CommandResult:
    """Typed execution outcome returned by command dispatchers and handlers."""

    status: CommandStatus
    code: str = ""
    message: str = ""
    matched_intent: Optional[Intent] = None
    execution_time_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    error_type: Optional[str] = None
    blocked_reason: Optional[BlockedReason] = None

    @property
    def is_success(self) -> bool:
        """True if command executed cleanly."""
        return self.status == CommandStatus.SUCCESS

    @classmethod
    def success(
        cls,
        intent: Optional[Intent] = None,
        message: str = "Command executed successfully",
        execution_time_ms: float = 0.0,
        **details: Any,
    ) -> CommandResult:
        """Convenience constructor for successful command results."""
        return cls(
            status=CommandStatus.SUCCESS,
            code="OK",
            message=message,
            matched_intent=intent,
            execution_time_ms=execution_time_ms,
            details=details,
        )

    @classmethod
    def no_match(
        cls,
        raw_text: str = "",
        message: str = "No matching command recognized",
        execution_time_ms: float = 0.0,
    ) -> CommandResult:
        """Convenience constructor when no valid intent matched."""
        return cls(
            status=CommandStatus.NO_MATCH,
            code="ERR_NO_MATCH",
            message=message,
            execution_time_ms=execution_time_ms,
            details={"raw_text": raw_text},
        )

    @classmethod
    def ambiguous(
        cls,
        candidates: list[Any],
        message: str = "Multiple ambiguous matches found",
        execution_time_ms: float = 0.0,
    ) -> CommandResult:
        """Convenience constructor when multiple target candidates exist."""
        return cls(
            status=CommandStatus.AMBIGUOUS,
            code="ERR_AMBIGUOUS",
            message=message,
            execution_time_ms=execution_time_ms,
            details={"candidates_count": len(candidates)},
        )

    @classmethod
    def element_gone(
        cls,
        element_id: int,
        message: str = "Target UI element is no longer visible or valid",
        execution_time_ms: float = 0.0,
    ) -> CommandResult:
        """Convenience constructor when target element was invalidated."""
        return cls(
            status=CommandStatus.ELEMENT_GONE,
            code="ERR_ELEMENT_GONE",
            message=message,
            execution_time_ms=execution_time_ms,
            details={"element_id": element_id},
        )

    @classmethod
    def blocked(
        cls,
        reason: BlockedReason,
        message: str,
        execution_time_ms: float = 0.0,
        **details: Any,
    ) -> CommandResult:
        """Convenience constructor when execution is blocked by security/policy."""
        return cls(
            status=CommandStatus.BLOCKED,
            code=f"ERR_BLOCKED_{reason.value.upper()}",
            message=message,
            blocked_reason=reason,
            execution_time_ms=execution_time_ms,
            details=details,
        )

    @classmethod
    def timeout(
        cls,
        message: str = "Operation exceeded maximum execution time budget",
        execution_time_ms: float = 0.0,
        **details: Any,
    ) -> CommandResult:
        """Convenience constructor for timeout events."""
        return cls(
            status=CommandStatus.TIMEOUT,
            code="ERR_TIMEOUT",
            message=message,
            execution_time_ms=execution_time_ms,
            details=details,
        )

    @classmethod
    def error(
        cls,
        exception: Exception,
        message: str = "",
        execution_time_ms: float = 0.0,
        **details: Any,
    ) -> CommandResult:
        """Convenience constructor for generic errors and exceptions."""
        return cls(
            status=CommandStatus.ERROR,
            code="ERR_INTERNAL",
            message=message or str(exception),
            error_type=type(exception).__name__,
            execution_time_ms=execution_time_ms,
            details={"exception": str(exception), **details},
        )


# ============================================================================
# Additional Supporting DTOs
# ============================================================================


@dataclass(slots=True)
class GridTarget:
    """Target cell inside a recursive 3x3 screen navigation grid."""

    cell_id: int
    row: int
    col: int
    rect: ScreenRect
    center: tuple[int, int]


@dataclass(slots=True)
class DisambiguationItem:
    """Candidate element assigned a disambiguation label (e.g. 'A', 'B', 'C')."""

    badge_label: str
    element: LabeledElement
    score: float = 1.0


@dataclass(slots=True)
class AudioChunk:
    """PCM audio buffer block ingested from WASAPI audio capture."""

    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    timestamp_ms: float = 0.0
    num_samples: int = 0

    def __post_init__(self) -> None:
        if self.num_samples == 0 and self.data:
            # 16-bit PCM = 2 bytes per sample per channel
            object.__setattr__(
                self,
                "num_samples",
                len(self.data) // (2 * max(1, self.channels)),
            )


@dataclass(slots=True)
class ConfirmationRequest:
    """Pending confirmation challenge for a high-risk voice action."""

    request_id: str
    prompt_message: str
    command_intent: Intent
    risk_level: str = "high"
    timeout_seconds: float = 5.0
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if this confirmation challenge has timed out."""
        return (time.time() - self.created_at) > self.timeout_seconds


# ============================================================================
# Concurrency & Cancellation Primitives
# ============================================================================


class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    def __init__(self) -> None:
        self._is_cancelled = threading.Event()
        self._callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Signal cancellation to all listeners."""
        with self._lock:
            if not self._is_cancelled.is_set():
                self._is_cancelled.set()
                for cb in self._callbacks:
                    try:
                        cb()
                    except Exception:
                        pass

    @property
    def is_cancelled(self) -> bool:
        """True if cancellation was requested."""
        return self._is_cancelled.is_set()

    def throw_if_cancelled(self) -> None:
        """Raise an OperationCancelled exception if cancelled."""
        if self.is_cancelled:
            from voxpilot.contracts.errors import CancellationError

            raise CancellationError("Operation cancelled by user or preemption")

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a cleanup hook to run immediately on cancellation."""
        with self._lock:
            if self._is_cancelled.is_set():
                callback()
            else:
                self._callbacks.append(callback)
