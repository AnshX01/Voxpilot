"""VoxPilot Standardized Exception Hierarchy."""

from __future__ import annotations

from typing import Optional


class VoxPilotError(Exception):
    """Base exception for all VoxPilot domain errors."""

    def __init__(self, message: str = "", code: str = "ERR_GENERIC") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ElementNotFoundError(VoxPilotError):
    """Raised when an element ID or label does not match any indexed element."""

    def __init__(self, identifier: str, message: str = "") -> None:
        msg = message or f"Element matching identifier '{identifier}' was not found"
        super().__init__(msg, code="ERR_ELEMENT_NOT_FOUND")
        self.identifier = identifier


class ElementGoneError(VoxPilotError):
    """Raised when a cached element is destroyed, scrolled offscreen, or unlinked."""

    def __init__(self, element_id: int, message: str = "") -> None:
        msg = message or f"Element #{element_id} was destroyed or moved offscreen"
        super().__init__(msg, code="ERR_ELEMENT_GONE")
        self.element_id = element_id


class AmbiguousCommandError(VoxPilotError):
    """Raised when multiple elements or interpretations match a single spoken command."""

    def __init__(self, candidate_count: int, message: str = "") -> None:
        msg = message or f"Ambiguous command: {candidate_count} candidates match"
        super().__init__(msg, code="ERR_AMBIGUOUS_MATCH")
        self.candidate_count = candidate_count


class BlockedActionError(VoxPilotError):
    """Base exception for commands blocked by security, integrity, or privacy boundaries."""

    def __init__(self, reason: str, message: str = "", code: str = "ERR_BLOCKED") -> None:
        msg = message or f"Action blocked by policy: {reason}"
        super().__init__(msg, code=code)
        self.reason = reason


class UIPIBlockedError(BlockedActionError):
    """Raised when User Interface Privilege Isolation blocks access to an elevated window."""

    def __init__(self, hwnd: int, message: str = "") -> None:
        msg = (
            message
            or f"Action blocked by UIPI on window HWND {hwnd}: target is running with Administrator integrity"
        )
        super().__init__(reason="UIPI", message=msg, code="ERR_BLOCKED_UIPI")
        self.hwnd = hwnd


class SecureDesktopBlockedError(BlockedActionError):
    """Raised when action cannot proceed because Windows Secure Desktop (UAC/Lock) is active."""

    def __init__(self, message: str = "") -> None:
        msg = message or "Action blocked: Windows Secure Desktop (UAC or Lock screen) is active"
        super().__init__(reason="SECURE_DESKTOP", message=msg, code="ERR_BLOCKED_SECURE_DESKTOP")


class PasswordFieldBlockedError(BlockedActionError):
    """Raised when voice text injection is prevented into a password field."""

    def __init__(self, message: str = "") -> None:
        msg = message or "Voice text injection blocked: focused control is a password field"
        super().__init__(reason="PASSWORD_FIELD", message=msg, code="ERR_BLOCKED_PASSWORD_FIELD")


class ConfirmationRequiredError(BlockedActionError):
    """Raised when a high-risk destructive action requires explicit voice confirmation."""

    def __init__(self, command_name: str, message: str = "") -> None:
        msg = message or f"Command '{command_name}' requires confirmation before execution"
        super().__init__(reason="REQUIRES_CONFIRMATION", message=msg, code="ERR_REQUIRES_CONFIRMATION")
        self.command_name = command_name


class RecognitionTimeoutError(VoxPilotError):
    """Raised when speech decoding or control tree traversal exceeds its time budget."""

    def __init__(self, elapsed_ms: float, budget_ms: float, message: str = "") -> None:
        msg = message or f"Operation timed out after {elapsed_ms:.1f}ms (budget: {budget_ms:.1f}ms)"
        super().__init__(msg, code="ERR_TIMEOUT")
        self.elapsed_ms = elapsed_ms
        self.budget_ms = budget_ms


class AudioDeviceError(VoxPilotError):
    """Raised on WASAPI capture device disconnection, buffer overrun, or access failure."""

    def __init__(self, device_name: str, message: str = "") -> None:
        msg = message or f"WASAPI audio device error on endpoint '{device_name}'"
        super().__init__(msg, code="ERR_AUDIO_DEVICE")
        self.device_name = device_name


class InputInjectionError(VoxPilotError):
    """Raised when Win32 SendInput fails to synthesize mouse or keyboard events."""

    def __init__(self, message: str = "", error_code: Optional[int] = None) -> None:
        msg = message or "Win32 SendInput synthesis failed"
        if error_code is not None:
            msg += f" (Win32 Error: {error_code})"
        super().__init__(msg, code="ERR_INPUT_INJECTION")
        self.error_code = error_code


class CancellationError(VoxPilotError):
    """Raised when an in-flight operation is cancelled cooperatively."""

    def __init__(self, message: str = "Operation cancelled by user or preemption") -> None:
        super().__init__(message, code="ERR_CANCELLED")
