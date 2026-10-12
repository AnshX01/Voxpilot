"""VoxPilot Core Interface Protocols.

Defines the clean architectural contracts between subsystems:
- Speech Recognition & Streaming
- Accessibility & UI Automation Discovery
- Hardware-Accelerated Overlay Display
- Low-Level Input Synthesis
- Natural Language Understanding & Parsing
- Dictation & Text Editing
- Window & Foreground Context
- Command Dispatch & Action Execution
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, runtime_checkable

from voxpilot.contracts.dto import (
    ActionType,
    AudioChunk,
    CancellationToken,
    CommandResult,
    DisambiguationItem,
    DisplayInfo,
    EngineMode,
    FocusState,
    Intent,
    LabeledElement,
    MouseButton,
    OverlayMode,
    ScreenRect,
    TranscriptEvent,
)


# ============================================================================
# Speech Engine Contract
# ============================================================================


@runtime_checkable
class ISpeechEngine(Protocol):
    """Low-latency streaming speech recognition interface.

    Responsible for:
    - Ingesting continuous PCM audio streams.
    - Emitting real-time partial hypotheses (<150ms) and final transcripts (<300ms).
    - Dynamically biasing recognition grammar with on-screen element hotwords.
    - Toggling between Command and Dictation engine modes.
    """

    def start(self) -> None:
        """Initialize models and start the internal recognition loop."""
        ...

    def stop(self) -> None:
        """Stop recognition worker and release engine resources."""
        ...

    def is_running(self) -> bool:
        """Check if the speech engine is actively processing audio."""
        ...

    def feed_audio(self, chunk: bytes) -> None:
        """Push a block of raw 16kHz 16-bit mono PCM audio bytes into the recognizer."""
        ...

    def set_grammar(self, words_or_phrases: list[str]) -> None:
        """Dynamically update recognizer grammar with visible UI element numbers and names."""
        ...

    def set_mode(self, mode: EngineMode) -> None:
        """Switch recognition mode between COMMAND and DICTATION."""
        ...

    def subscribe_transcripts(self, callback: Callable[[TranscriptEvent], None]) -> None:
        """Register a callback for streaming partial and final transcript events."""
        ...

    def unsubscribe_transcripts(self, callback: Callable[[TranscriptEvent], None]) -> None:
        """Remove a previously registered transcript event listener."""
        ...

    def get_latency_metrics(self) -> dict[str, float]:
        """Return diagnostic metrics (e.g. first_partial_latency_ms, avg_rtf)."""
        ...


# ============================================================================
# UI Automation & Element Provider Contract
# ============================================================================


@runtime_checkable
class IElementProvider(Protocol):
    """UI Automation element discovery and indexing interface.

    Responsible for:
    - Walking interactive control trees of active top-level windows.
    - Filtering visible, clickable, and actionable controls.
    - Waking up dormant Chromium/Electron accessibility trees via WM_GETOBJECT.
    - Computing deterministic stability keys for dynamic web apps.
    - Maintaining the active in-memory spatial index.
    """

    def discover_elements(
        self,
        window_handle: Optional[int] = None,
        screen_rect: Optional[ScreenRect] = None,
    ) -> list[LabeledElement]:
        """Enumerate interactive controls for target window or screen bounds."""
        ...

    def filter_visible_actionable(
        self, elements: list[LabeledElement]
    ) -> list[LabeledElement]:
        """Filter out off-screen, obscured, or non-actionable elements."""
        ...

    def compute_stability_key(self, element: LabeledElement) -> str:
        """Generate deterministic SHA-256 hash identifying the element across re-renders."""
        ...

    def activate_chromium_window(self, hwnd: int) -> bool:
        """Wake up Chromium accessibility tree by dispatching WM_GETOBJECT to render host."""
        ...

    def get_element_by_id(self, element_id: int) -> Optional[LabeledElement]:
        """Lookup an element from the active spatial index by its assigned number."""
        ...

    def get_element_by_stability_key(self, key: str) -> Optional[LabeledElement]:
        """Lookup an element by its persistent stability key."""
        ...

    def invalidate_cache(self) -> None:
        """Clear active element index and cached UI Automation COM pointers."""
        ...


# ============================================================================
# Overlay Service Contract
# ============================================================================


@runtime_checkable
class IOverlayService(Protocol):
    """Hardware-accelerated non-activating overlay presentation interface.

    Responsible for:
    - Painting numbered badges (1..999) over actionable UI elements (<1ms paint).
    - Displaying element name tags and disambiguation badges ('A', 'B', 'C').
    - Projecting a 3x3 recursive navigation grid.
    - Projecting the non-activating Heads-Up Display (HUD) toast banner.
    - Ensuring zero focus theft (WS_EX_NOACTIVATE) and full click-through (WS_EX_TRANSPARENT).
    """

    def show_numbers(self, elements: list[LabeledElement]) -> None:
        """Render numbered badges over the provided elements."""
        ...

    def show_names(self, elements: list[LabeledElement]) -> None:
        """Render label name badges over matching elements."""
        ...

    def show_grid(
        self,
        display_id: Optional[str] = None,
        sub_rect: Optional[ScreenRect] = None,
    ) -> None:
        """Render a 3x3 numbered mouse navigation grid across screen or sub-rectangle."""
        ...

    def show_disambiguation(
        self,
        items: list[DisambiguationItem],
        target_rect: Optional[ScreenRect] = None,
    ) -> None:
        """Render lettered disambiguation badges over multiple candidate matches."""
        ...

    def show_hud(
        self,
        message: str,
        duration_ms: int = 2000,
        level: str = "info",
    ) -> None:
        """Display an ephemeral non-activating status toast banner."""
        ...

    def hide(self) -> None:
        """Clear all active badges, grids, and overlays from the display."""
        ...

    def is_visible(self) -> bool:
        """Check if any overlay layer is currently displayed."""
        ...

    def current_mode(self) -> OverlayMode:
        """Return the currently displayed overlay mode."""
        ...


# ============================================================================
# Input Injector Contract
# ============================================================================


@runtime_checkable
class IInputInjector(Protocol):
    """Low-level Win32 synthetic input injection interface.

    Responsible for:
    - Absolute mouse cursor positioning across virtual desktop space.
    - Mouse clicks, double clicks, right clicks, drags, and scrolling.
    - Keyboard presses, hotkeys, and Unicode character stream injection.
    - Enforcing stuck-modifier cleanup invariants.
    """

    def mouse_move(self, x: int, y: int) -> bool:
        """Move cursor to virtual screen coordinates (x, y)."""
        ...

    def mouse_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: MouseButton = MouseButton.LEFT,
        count: int = 1,
    ) -> bool:
        """Click the mouse button at specified or current coordinates."""
        ...

    def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 200,
    ) -> bool:
        """Perform a smooth drag-and-drop gesture from start to end coordinates."""
        ...

    def mouse_scroll(self, delta_y: int, delta_x: int = 0) -> bool:
        """Synthesize vertical and optional horizontal mouse wheel ticks."""
        ...

    def key_down(self, key: str) -> bool:
        """Synthesize key depression event."""
        ...

    def key_up(self, key: str) -> bool:
        """Synthesize key release event."""
        ...

    def key_press(self, key: str) -> bool:
        """Synthesize discrete key tap (press down and up)."""
        ...

    def key_combination(self, keys: list[str]) -> bool:
        """Synthesize compound shortcut (e.g. ['ctrl', 'shift', 'p'])."""
        ...

    def type_unicode(self, text: str) -> bool:
        """Inject arbitrary Unicode text using KEYEVENTF_UNICODE."""
        ...

    def release_all_modifiers(self) -> None:
        """Ensure all modifier keys (Shift, Ctrl, Alt, Win) are in released state."""
        ...


# ============================================================================
# Command Parser & NLU Contract
# ============================================================================


@runtime_checkable
class ICommandParser(Protocol):
    """Natural Language Understanding and rule parsing interface.

    Responsible for:
    - Matching spoken transcripts against registered command grammar patterns.
    - Normalizing spoken numbers 1-999 ('forty two' -> 42).
    - Extracting intent names, target slots, and confidence scores.
    - Fuzzy matching spoken names against visible UI element titles.
    """

    def parse(
        self,
        text: str,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[Intent]:
        """Parse raw speech text into an actionable structured Intent."""
        ...

    def parse_number(self, text_token: str) -> Optional[int]:
        """Convert a spoken numerical phrase ('twenty three') or digits ('23') to an integer (1-999)."""
        ...

    def get_registered_patterns(self) -> list[str]:
        """Return list of supported voice command template strings."""
        ...

    def register_dynamic_keywords(self, keywords: list[str]) -> None:
        """Expand grammar lexicon with dynamic on-screen keywords."""
        ...

    def match_element_label(
        self,
        spoken_label: str,
        candidates: list[LabeledElement],
    ) -> list[tuple[LabeledElement, float]]:
        """Fuzzy-match spoken label against candidate elements, returning ranked scores."""
        ...


# ============================================================================
# Dictation Service Contract
# ============================================================================


@runtime_checkable
class IDictationService(Protocol):
    """Continuous text dictation and voice editing interface.

    Responsible for:
    - Receiving speech bursts from the DictationEngine.
    - Applying punctuation, capitalization, and formatting rules.
    - Executing spoken editing commands ('scratch that', 'capitalize next', 'new line').
    - Verifying focus target validity and password protection before injecting text.
    """

    def handle_burst(self, transcript: TranscriptEvent) -> CommandResult:
        """Process and inject a recognized dictation text burst."""
        ...

    def apply_formatting(
        self,
        raw_text: str,
        formatting_rules: Optional[dict[str, Any]] = None,
    ) -> str:
        """Apply formatting transforms (capitalization, spacing, symbols) to raw transcript."""
        ...

    def execute_editing_command(self, command: str) -> CommandResult:
        """Execute spoken text editing directives (e.g. 'delete last word', 'select all')."""
        ...

    def verify_focus_target(self) -> bool:
        """Verify that focused control can safely receive text (not a password field)."""
        ...

    def is_active(self) -> bool:
        """Check if dictation mode is actively accepting speech."""
        ...


# ============================================================================
# Context & Foreground Window Service Contract
# ============================================================================


@runtime_checkable
class IContextService(Protocol):
    """System context, window topology, and security inspection interface.

    Responsible for:
    - Inspecting active foreground window handle and process credentials.
    - Tracking caret position and focused control bounds.
    - Detecting password fields (ES_PASSWORD, UIA_IsPasswordPropertyId).
    - Detecting secure desktop state (UAC elevation / Lock screen).
    - Querying multi-monitor display metrics and DPI scale factors.
    """

    def get_foreground_window(self) -> int:
        """Return HWND handle of active foreground top-level window."""
        ...

    def get_focus_state(self) -> FocusState:
        """Inspect and return current focus target and security state."""
        ...

    def is_password_focused(self) -> bool:
        """Check if active focus is currently on a secure password field."""
        ...

    def is_secure_desktop(self) -> bool:
        """Check if the active desktop station is a Secure Desktop (UAC / Lock)."""
        ...

    def get_displays(self) -> list[DisplayInfo]:
        """Return display geometry and DPI scaling for all connected monitors."""
        ...

    def subscribe_focus_changed(self, callback: Callable[[FocusState], None]) -> None:
        """Register hook for foreground window or keyboard focus change events."""
        ...

    def unsubscribe_focus_changed(
        self, callback: Callable[[FocusState], None]
    ) -> None:
        """Unregister focus change event listener."""
        ...


# ============================================================================
# Command Dispatcher & Element Action Contracts
# ============================================================================


@runtime_checkable
class ICommandDispatcher(Protocol):
    """Central router coordinating intent validation and subsystem dispatch."""

    def dispatch(
        self,
        intent: Intent,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CommandResult:
        """Execute intent across appropriate subsystem with safety checks and timeout."""
        ...

    def register_handler(
        self,
        action_name: str,
        handler: Callable[..., CommandResult],
    ) -> None:
        """Register custom command handler for specific action intent."""
        ...


@runtime_checkable
class IElementActionService(Protocol):
    """UI Automation pattern invocation and element execution service."""

    def execute_action(
        self,
        element: LabeledElement,
        action: ActionType,
    ) -> CommandResult:
        """Invoke native UIA pattern or fall back to coordinate input synthesis."""
        ...

    def supports_action(
        self,
        element: LabeledElement,
        action: ActionType,
    ) -> bool:
        """Check if an element natively supports an action pattern."""
        ...


# ============================================================================
# Audio Capture & User Feedback Contracts
# ============================================================================


@runtime_checkable
class IAudioCaptureService(Protocol):
    """WASAPI audio stream ingestion interface."""

    def start(self) -> None:
        """Start capturing audio from the default WASAPI capture device."""
        ...

    def stop(self) -> None:
        """Stop audio capture client."""
        ...

    def is_recording(self) -> bool:
        """Check if capture client is running."""
        ...

    def read_chunk(self) -> Optional[AudioChunk]:
        """Fetch next 100ms PCM chunk from ring buffer, or None if buffer is empty."""
        ...


@runtime_checkable
class IFeedbackService(Protocol):
    """User auditory and visual feedback presentation interface."""

    def play_earcon(self, cue_name: str) -> None:
        """Play low-latency auditory cue (e.g. 'success', 'error', 'wake', 'sleep')."""
        ...

    def show_hud_message(
        self,
        message: str,
        duration_ms: int = 2000,
        level: str = "info",
    ) -> None:
        """Present ephemeral HUD banner to user."""
        ...
