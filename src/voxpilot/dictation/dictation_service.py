"""VoxPilot Dictation Service Implementation.

Integrates formatting rules, spoken editing, focus verification,
and atomic undo-able text bursts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import logging
import time
from typing import Any, Optional

from ..contracts.dto import (
    BlockedReason,
    CommandResult,
    CommandStatus,
    EngineMode,
    TranscriptEvent,
)
from ..contracts.interfaces import (
    IContextService,
    IDictationService,
    IInputInjector,
)
from .editing import EditingEngine
from .formatting import FormattingEngine

logger = logging.getLogger("voxpilot.dictation.service")


@dataclass(slots=True)
class DictationBurstRecord:
    """Historical record of an injected dictation burst for undo operations."""

    text: str
    char_count: int
    timestamp: float = field(default_factory=time.time)
    window_handle: int = 0


class DictationService(IDictationService):
    """Production implementation of IDictationService."""

    def __init__(
        self,
        injector: IInputInjector,
        context_service: Optional[IContextService] = None,
        max_history: int = 100,
    ) -> None:
        self.injector = injector
        self.context_service = context_service
        self.formatting_engine = FormattingEngine()
        self.editing_engine = EditingEngine(injector)

        self._active: bool = False
        self._spelling_mode: bool = False
        self._history: deque[DictationBurstRecord] = deque(maxlen=max_history)

    def is_active(self) -> bool:
        """Check if dictation mode is actively accepting speech."""
        return self._active

    def set_active(self, active: bool) -> None:
        """Enable or disable active dictation input."""
        self._active = active
        if not active:
            self.formatting_engine.reset_state()

    def set_spelling_mode(self, enabled: bool) -> None:
        """Toggle spelling (NATO phonetic) mode."""
        self._spelling_mode = enabled

    def verify_focus_target(self) -> bool:
        """Verify that focused control can safely receive text (not a password field or secure desktop)."""
        if self.context_service is None:
            return True

        try:
            if self.context_service.is_secure_desktop():
                logger.warning("Focus check failed: Secure desktop active.")
                return False

            if self.context_service.is_password_focused():
                logger.warning("Focus check failed: Focus is on a password field.")
                return False

            return True
        except Exception as exc:
            logger.error("Error during focus target verification: %s", exc)
            return True

    def apply_formatting(
        self,
        raw_text: str,
        formatting_rules: Optional[dict[str, Any]] = None,
    ) -> str:
        """Apply formatting transforms (capitalization, spacing, symbols) to raw transcript."""
        return self.formatting_engine.format_text(
            raw_text=raw_text,
            spelling_mode=self._spelling_mode,
            rules=formatting_rules,
        )

    def execute_editing_command(self, command: str) -> CommandResult:
        """Execute spoken text editing directives (e.g. 'delete last word', 'select all')."""
        last_len = self._history[-1].char_count if self._history else 0
        result = self.editing_engine.execute_command(command, last_burst_len=last_len)
        if result.status == CommandStatus.SUCCESS:
            cmd_lower = command.lower().strip()
            if cmd_lower in ("scratch that", "delete that", "undo that") and self._history:
                self._history.pop()
        return result

    def handle_burst(self, transcript: TranscriptEvent) -> CommandResult:
        """Process and inject a recognized dictation text burst."""
        if not self._active:
            return CommandResult.blocked(
                reason=BlockedReason.REQUIRES_CONFIRMATION,
                message="Dictation mode is currently inactive",
            )

        raw_text = transcript.text.strip()
        if not raw_text:
            return CommandResult.no_match(raw_text="", message="Empty dictation burst")

        # 1. Check if the burst is a spoken editing directive
        if self.editing_engine.is_editing_command(raw_text):
            return self.execute_editing_command(raw_text)

        # 2. Verify Focus Safety
        if not self.verify_focus_target():
            reason = BlockedReason.PASSWORD_FIELD
            if self.context_service and self.context_service.is_secure_desktop():
                reason = BlockedReason.SECURE_DESKTOP
            return CommandResult.blocked(
                reason=reason,
                message="Text injection blocked: secure desktop or password field detected",
            )

        # 3. Apply text normalization, punctuation, and capitalization
        formatted_text = self.apply_formatting(raw_text)
        if not formatted_text:
            return CommandResult.success(message="No printable text produced")

        # 4. Inject text into focused control
        start_t = time.perf_counter()
        target_hwnd = self.context_service.get_foreground_window() if self.context_service else 0
        success = self.injector.type_unicode(formatted_text)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        if not success:
            return CommandResult.error(
                RuntimeError("Type injection failed"),
                message="Failed to inject text via input injector",
                execution_time_ms=elapsed_ms,
            )

        # 5. Record burst into undo history
        self._history.append(
            DictationBurstRecord(
                text=formatted_text,
                char_count=len(formatted_text),
                window_handle=target_hwnd,
            )
        )

        return CommandResult.success(
            message=f"Dictated: '{formatted_text}'",
            execution_time_ms=elapsed_ms,
            details={"char_count": len(formatted_text)},
        )
