"""
VoxPilot Core Engine & Dispatcher
Ties together Audio/FakeMic -> Speech Engine -> Command Parser -> Automation -> Overlay -> Input Injection.
"""

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Optional, List, Dict, Any

from voxpilot.contracts.dto import (
    EngineMode,
    TranscriptEvent,
    Intent,
    CommandResult,
    CommandStatus,
    BlockedReason,
    LabeledElement,
    MouseButton,
    ScreenRect,
)
from voxpilot.speech import VoskSpeechEngine, LiveAudioCapture, FakeMic
from voxpilot.commands import CommandParser, NumberParser
from voxpilot.automation import UiaElementProvider
from voxpilot.overlay import OverlayService
from voxpilot.input import WindowsInputInjector
from voxpilot.dictation.dictation_service import DictationService

user32 = ctypes.windll.user32
logger = logging.getLogger("VoxPilot")

class VoxPilotEngine:
    """End-to-end voice control engine coordinating speech, NLU, automation, and overlay."""

    def __init__(
        self,
        speech_engine: Optional[VoskSpeechEngine] = None,
        command_parser: Optional[CommandParser] = None,
        element_provider: Optional[UiaElementProvider] = None,
        overlay_service: Optional[OverlayService] = None,
        input_injector: Optional[WindowsInputInjector] = None,
    ) -> None:
        self.speech_engine = speech_engine or VoskSpeechEngine()
        self.command_parser = command_parser or CommandParser()
        self.element_provider = element_provider or UiaElementProvider()
        self.overlay_service = overlay_service or OverlayService()
        self.input_injector = input_injector or WindowsInputInjector()

        try:
            from voxpilot.automation.context_service import ContextService
            _ctx = ContextService()
        except Exception:
            _ctx = None
        self.dictation_service = DictationService(self.input_injector, context_service=_ctx)
        from voxpilot.textnav import TextNumbering, SwiftFormatter
        from voxpilot.automation.text_target import FocusedTextTarget
        self.text_numbering = TextNumbering(FocusedTextTarget())
        self.swift_formatter = SwiftFormatter()
        self._mode = EngineMode.DICTATION
        # Voice Control starts in Dictation mode (Apple guide: "Dictation mode is on by default").
        self.mode = EngineMode.DICTATION
        self.is_running = False
        self._last_result: Optional[CommandResult] = None
        self._history: List[CommandResult] = []
        self._lock = threading.RLock()

        self._live_capture: Optional[LiveAudioCapture] = None
        self._capture_thread: Optional[threading.Thread] = None

        self.speech_engine.subscribe(self._on_transcript)

    def start(self, live_mic: bool = False, device_id: Optional[int] = None) -> None:
        self.is_running = True
        self.speech_engine.start()
        self.overlay_service.update_hud(mode=self.mode, text="Ready")
        if live_mic:
            self.start_live_capture(device_id=device_id)

    def start_live_capture(self, device_id: Optional[int] = None) -> bool:
        """Start WASAPI microphone capture streaming audio chunks to speech engine."""
        try:
            self._live_capture = LiveAudioCapture()
            self._live_capture.start(device_id=device_id)
            self._capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
            self._capture_thread.start()
            logger.info("Live microphone capture started successfully.")
            return True
        except Exception as exc:
            logger.warning(f"Could not start live microphone capture: {exc}")
            self._live_capture = None
            return False

    def _capture_worker(self) -> None:
        while self.is_running and self._live_capture and self._live_capture.is_running:
            chunk = self._live_capture.read_chunk(timeout=0.2)
            if chunk:
                self.speech_engine.process_audio(chunk)

    def stop_live_capture(self) -> None:
        if self._live_capture:
            self._live_capture.stop()
            self._live_capture = None

    def stop(self) -> None:
        self.is_running = False
        self.stop_live_capture()
        self.speech_engine.stop()
        self.overlay_service.hide_all()
        self.input_injector.release_all_modifiers()

    def process_text_command(self, phrase: str) -> CommandResult:
        """Direct injection of phrase (e.g. for testing, fake-mic, or CLI 'voxpilot say')."""
        with self._lock:
            t0 = time.perf_counter()
            intent = self.command_parser.parse(phrase)
            if not intent:
                res = CommandResult.no_match(raw_text=phrase, execution_time_ms=(time.perf_counter() - t0) * 1000)
                self._record_result(res)
                return res

            res = self.dispatch_intent(intent)
            res.execution_time_ms = (time.perf_counter() - t0) * 1000
            self._record_result(res)
            return res

    def _on_transcript(self, event: TranscriptEvent) -> None:
        if not event.is_final:
            self.overlay_service.update_hud(mode=self.mode, text=event.text)
            return

        text = event.text.strip()
        if not text or text == "[unk]":
            return

        logger.info(f"Final transcript: '{text}' in mode {self.mode}")

        if self.mode in (EngineMode.DICTATION, EngineMode.SPELLING, EngineMode.SWIFT):
            self._handle_text_entry(text)
            return

        # In COMMAND Mode:
        tres = self._try_text_number_command(text)
        if tres is not None:
            self._record_result(tres)
            return
        res = self.process_text_command(text)
        # If it was casual conversation (NO_MATCH), take zero action and do not pop up errors
        if res.status == CommandStatus.NO_MATCH:
            logger.debug(f"Filtered non-command utterance: '{text}'")
            return

    _TEXT_OPS = r"(delete|uppercase|lowercase|capitalize|select)"

    @property
    def mode(self) -> EngineMode:
        return self._mode

    @mode.setter
    def mode(self, value: EngineMode) -> None:
        self._mode = value
        se = getattr(self, "speech_engine", None)
        setter = getattr(se, "set_open_vocabulary", None)
        if setter:
            try:
                setter(value in (EngineMode.DICTATION, EngineMode.SPELLING, EngineMode.SWIFT))
            except Exception:  # pragma: no cover
                logger.exception("could not switch recognizer vocabulary")

    def _handle_show_text_numbers(self, intent: Intent) -> CommandResult:
        items = self.text_numbering.show()
        if not items:
            self.text_numbering.hide()
            return CommandResult.error(exception=RuntimeError("no text input area focused"),
                                       message="No text input area with text to number")
        self._paint_text_numbers()
        return CommandResult.success(intent=intent, message=f"Text numbers shown ({len(items)})")

    def _paint_text_numbers(self) -> None:
        show = getattr(self.overlay_service, "show_text_numbers", None)
        if not show:
            return
        from dataclasses import replace
        rects = getattr(self.text_numbering.target, "item_rects", None)
        items = self.text_numbering.items
        if rects:
            try:
                rs = rects(items)
                items = [replace(it, rect=r) for it, r in zip(items, rs)]
            except Exception:
                pass
        show(items)

    def _try_text_number_command(self, text: str) -> Optional[CommandResult]:
        """'<delete|uppercase|lowercase|capitalize|select> <n>' while text numbers are shown."""
        import re
        from voxpilot.commands.number_parser import NumberParser
        if not self.text_numbering.visible:
            return None
        m = re.match(r"^" + self._TEXT_OPS + r"\s+(.+)$", text.strip().lower())
        if not m:
            return None
        n = NumberParser.parse_number_phrase(m.group(2))
        if n is None:
            return None
        op = m.group(1)
        tn = self.text_numbering
        if op == "select":
            ok = tn.select(n)
        else:
            it = tn.get(n)
            ok = bool(it) and tn.apply(op, n)
            if ok:
                new = tn.transform(op, it.text)
                if op == "delete":
                    self.input_injector.key_press("delete")
                else:
                    self.input_injector.type_unicode(new)
                tn.level = "line"
                tn.refresh()
        if not ok:
            return CommandResult.error(exception=ValueError(f"no text item {n}"), message=f"No text item {n}")
        self._paint_text_numbers()
        return CommandResult.success(message=f"{op} {n}")

    def _handle_text_entry(self, text: str) -> None:
        res = self._try_text_number_command(text)
        if res is not None:
            self._record_result(res)
            return
        """Dictation/Spelling/Swift: commands win, anything else is entered as text."""
        svc = self.dictation_service
        svc.set_active(True)
        svc.set_spelling_mode(self.mode == EngineMode.SPELLING)
        if svc.editing_engine.is_editing_command(text):
            svc.execute_editing_command(text)
            return
        intent = self.command_parser.parse(text)
        if intent:
            self.process_text_command(text)
            return
        if self.mode == EngineMode.SWIFT:
            if not svc.verify_focus_target():
                return
            code = self.swift_formatter.format(text)
            if code:
                self.input_injector.type_unicode(code)
            return
        svc.handle_burst(TranscriptEvent(text=text, is_final=True))

    def dispatch_intent(self, intent: Intent) -> CommandResult:
        name = intent.name

        # When in SLEEP mode, block all intents except WAKE_UP
        if self.mode == EngineMode.SLEEP and name != "WAKE_UP":
            return CommandResult.blocked(
                reason=BlockedReason.SECURE_DESKTOP,
                message="Voice Control is paused. Say 'Start listening' to resume.",
            )

        if name == "SHOW_NUMBERS":
            return self._handle_show_numbers(intent, continuous=False)
        elif name == "SHOW_NUMBERS_CONTINUOUS":
            return self._handle_show_numbers(intent, continuous=True)
        elif name == "HIDE_NUMBERS":
            return self._handle_hide_numbers(intent)
        elif name == "SHOW_WINDOW_NUMBERS":
            return self._handle_show_window_numbers(intent)
        elif name == "SHOW_NAMES" or name == "SHOW_NAMES_CONTINUOUS":
            return self._handle_show_names(intent)
        elif name == "HIDE_NAMES":
            return self._handle_hide_names(intent)
        elif name == "CLICK":
            self.input_injector.click(MouseButton.LEFT, count=1)
            return CommandResult.success(intent=intent, message="Clicked cursor position")
        elif name == "DOUBLE_CLICK":
            self.input_injector.click(MouseButton.LEFT, count=2)
            return CommandResult.success(intent=intent, message="Double clicked cursor position")
        elif name == "TRIPLE_CLICK":
            pos = self.input_injector.get_cursor_position()
            self.input_injector.triple_click_at(pos[0], pos[1])
            return CommandResult.success(intent=intent, message="Triple clicked cursor position")
        elif name == "RIGHT_CLICK":
            self.input_injector.click(MouseButton.RIGHT, count=1)
            return CommandResult.success(intent=intent, message="Right clicked cursor position")
        elif name == "LONG_PRESS":
            pos = self.input_injector.get_cursor_position()
            self.input_injector.long_press_at(pos[0], pos[1], duration_s=1.2)
            return CommandResult.success(intent=intent, message="Long pressed cursor position")
        elif name == "CLICK_NUMBER":
            return self._handle_click_number(intent)
        elif name == "DOUBLE_CLICK_NUMBER":
            return self._handle_click_number(intent, count=2)
        elif name == "TRIPLE_CLICK_NUMBER":
            return self._handle_click_number(intent, count=3)
        elif name == "RIGHT_CLICK_NUMBER":
            return self._handle_click_number(intent, button=MouseButton.RIGHT)
        elif name == "LONG_PRESS_NUMBER":
            return self._handle_long_press_number(intent)
        elif name == "DRAG_NUMBER":
            return self._handle_drag_number(intent)
        elif name == "START_DRAG_NUMBER":
            return self._handle_start_drag_number(intent)
        elif name == "DROP":
            self.input_injector.mouse_up(MouseButton.LEFT)
            return CommandResult.success(intent=intent, message="Dropped item")
        elif name == "MOVE_CURSOR":
            return self._handle_move_cursor(intent)
        elif name == "CLICK_NAME":
            return self._handle_click_name(intent)
        elif name == "SWITCH_TO_COMMAND_MODE":
            self.mode = EngineMode.COMMAND
            self.overlay_service.update_hud(mode=self.mode, text="Command Mode Active")
            return CommandResult.success(intent=intent, message="Switched to Command mode")
        elif name == "SWITCH_TO_DICTATION_MODE":
            self.mode = EngineMode.DICTATION
            self.overlay_service.update_hud(mode=self.mode, text="Dictation Active")
            return CommandResult.success(intent=intent, message="Switched to Dictation mode")
        elif name == "SHOW_TEXT_NUMBERS":
            return self._handle_show_text_numbers(intent)
        elif name == "HIDE_TEXT_NUMBERS":
            self.text_numbering.hide()
            self.overlay_service.hide_text_numbers() if hasattr(self.overlay_service, "hide_text_numbers") else None
            return CommandResult.success(intent=intent, message="Text numbers hidden")
        elif name == "SWITCH_TO_SPELLING_MODE":
            self.mode = EngineMode.SPELLING
            self.overlay_service.update_hud(mode=self.mode, text="Spelling Mode Active")
            return CommandResult.success(intent=intent, message="Switched to Spelling mode")
        elif name == "SWITCH_TO_SWIFT_MODE":
            self.mode = EngineMode.SWIFT
            self.overlay_service.update_hud(mode=self.mode, text="Swift Mode Active")
            return CommandResult.success(intent=intent, message="Switched to Swift mode")
        elif name == "SHOW_GRID":
            self.overlay_service.show_grid()
            self.overlay_service.update_hud(mode=self.mode, text="Grid Visible")
            return CommandResult.success(intent=intent, message="Grid displayed")
        elif name == "SHOW_WINDOW_GRID":
            return self._handle_show_window_grid(intent)
        elif name == "HIDE_GRID":
            self.overlay_service.hide_grid()
            self.overlay_service.update_hud(mode=self.mode, text="Grid Hidden")
            return CommandResult.success(intent=intent, message="Grid hidden")
        elif name == "SCROLL":
            direction = str(intent.slots.get("direction", "down")).lower()
            if direction not in ("up", "down", "left", "right"):
                return CommandResult.error(exception=ValueError(f"Invalid scroll direction: {direction}"))
            raw_amount = intent.slots.get("amount", 120)
            try:
                amount = int(raw_amount)
            except (ValueError, TypeError) as e:
                return CommandResult.error(exception=e, message="Invalid scroll amount")

            from voxpilot.contracts.dto import ScrollDirection
            sd = ScrollDirection.DOWN if direction == "down" else ScrollDirection.UP
            self.input_injector.scroll(direction=sd, amount=amount)
            return CommandResult.success(intent=intent, message=f"Scrolled {direction}")
        elif name == "WAKE_UP":
            self.mode = EngineMode.COMMAND
            self.overlay_service.update_hud(mode=self.mode, text="Awake")
            return CommandResult.success(intent=intent, message="VoxPilot awake")
        elif name == "GO_TO_SLEEP":
            self.mode = EngineMode.SLEEP
            self.overlay_service.hide_all()
            self.overlay_service.update_hud(mode=self.mode, text="Sleeping")
            return CommandResult.success(intent=intent, message="VoxPilot sleeping")
        elif name == "START_DICTATION":
            self.mode = EngineMode.DICTATION
            self.overlay_service.update_hud(mode=self.mode, text="Dictation Active")
            return CommandResult.success(intent=intent, message="Switched to Dictation mode")
        elif name == "STOP_DICTATION":
            self.mode = EngineMode.COMMAND
            self.overlay_service.update_hud(mode=self.mode, text="Command Mode Active")
            return CommandResult.success(intent=intent, message="Switched to Command mode")
        elif name == "SHOW_COMMANDS":
            from voxpilot.app.command_catalog import commands_for_context
            ctx = "text" if self.mode in (EngineMode.DICTATION, EngineMode.SPELLING, EngineMode.SWIFT) else "general"
            self.visible_commands = commands_for_context(ctx)
            show = getattr(self.overlay_service, "show_commands_window", None)
            if show:
                show(self.visible_commands)
            return CommandResult.success(intent=intent, message="Displayed voice commands")
        elif name == "HIDE_COMMANDS":
            self.overlay_service.hide()
            self.overlay_service.update_hud(mode=self.mode, text="Commands Hidden")
            return CommandResult.success(intent=intent, message="Commands hidden")
        elif name == "MUTE":
            self.mode = EngineMode.SLEEP
            self.overlay_service.hide_all()
            self.overlay_service.update_hud(mode=self.mode, text="Microphone Muted")
            return CommandResult.success(intent=intent, message="Microphone muted")
        elif name == "UNMUTE":
            self.mode = EngineMode.COMMAND
            self.overlay_service.update_hud(mode=self.mode, text="Microphone Active")
            return CommandResult.success(intent=intent, message="Microphone unmuted")
        elif name == "DELETE_LAST_WORD":
            self.input_injector.key_combination(["ctrl", "backspace"])
            return CommandResult.success(intent=intent, message="Deleted last word")
        elif name == "SCROLL_TOP":
            self.input_injector.key_combination(["ctrl", "home"])
            return CommandResult.success(intent=intent, message="Scrolled to top")
        elif name == "SCROLL_BOTTOM":
            self.input_injector.key_combination(["ctrl", "end"])
            return CommandResult.success(intent=intent, message="Scrolled to bottom")
        elif name == "SNAP_WINDOW_LEFT":
            self.input_injector.key_combination(["win", "left"])
            return CommandResult.success(intent=intent, message="Snapped left")
        elif name == "SNAP_WINDOW_RIGHT":
            self.input_injector.key_combination(["win", "right"])
            return CommandResult.success(intent=intent, message="Snapped right")
        elif name == "SNAP_WINDOW_UP":
            self.input_injector.key_combination(["win", "up"])
            return CommandResult.success(intent=intent, message="Snapped up")
        elif name == "SNAP_WINDOW_DOWN":
            self.input_injector.key_combination(["win", "down"])
            return CommandResult.success(intent=intent, message="Snapped down")
        elif name == "SWITCH_APP":
            self.input_injector.key_combination(["alt", "tab"])
            return CommandResult.success(intent=intent, message="Switched application")
        elif name == "TASK_VIEW":
            self.input_injector.key_combination(["win", "tab"])
            return CommandResult.success(intent=intent, message="Task view opened")
        elif name == "NEXT_DESKTOP":
            self.input_injector.key_combination(["ctrl", "win", "right"])
            return CommandResult.success(intent=intent, message="Switched to next desktop")
        elif name == "PREVIOUS_DESKTOP":
            self.input_injector.key_combination(["ctrl", "win", "left"])
            return CommandResult.success(intent=intent, message="Switched to previous desktop")
        elif name == "PAGE_UP":
            self.input_injector.key_press("pageup")
            return CommandResult.success(intent=intent, message="Page up")
        elif name == "PAGE_DOWN":
            self.input_injector.key_press("pagedown")
            return CommandResult.success(intent=intent, message="Page down")
        elif name == "CLOSE_WINDOW":
            self.input_injector.key_combination(["alt", "f4"])
            return CommandResult.success(intent=intent, message="Closed window")
        elif name == "MINIMIZE_WINDOW":
            self.input_injector.key_combination(["win", "down"])
            return CommandResult.success(intent=intent, message="Minimized window")
        elif name == "MAXIMIZE_WINDOW":
            self.input_injector.key_combination(["win", "up"])
            return CommandResult.success(intent=intent, message="Maximized window")
        elif name == "RESTORE_WINDOW":
            self.input_injector.key_combination(["win", "down"])
            return CommandResult.success(intent=intent, message="Restored window")
        elif name == "SHOW_DESKTOP":
            self.input_injector.key_combination(["win", "d"])
            return CommandResult.success(intent=intent, message="Showed desktop")
        elif name == "PRESS_ENTER":
            self.input_injector.key_press("enter")
            return CommandResult.success(intent=intent, message="Pressed enter")
        elif name == "PRESS_ESCAPE":
            self.input_injector.key_press("escape")
            return CommandResult.success(intent=intent, message="Pressed escape")
        elif name == "PRESS_TAB":
            self.input_injector.key_press("tab")
            return CommandResult.success(intent=intent, message="Pressed tab")
        elif name == "PRESS_BACKSPACE":
            self.input_injector.key_press("backspace")
            return CommandResult.success(intent=intent, message="Pressed backspace")
        elif name == "COPY":
            self.input_injector.key_combination(["ctrl", "c"])
            return CommandResult.success(intent=intent, message="Copied")
        elif name == "CUT":
            self.input_injector.key_combination(["ctrl", "x"])
            return CommandResult.success(intent=intent, message="Cut")
        elif name == "PASTE":
            self.input_injector.key_combination(["ctrl", "v"])
            return CommandResult.success(intent=intent, message="Pasted")
        elif name == "SELECT_ALL":
            self.input_injector.key_combination(["ctrl", "a"])
            return CommandResult.success(intent=intent, message="Selected all")
        elif name == "UNDO":
            self.input_injector.key_combination(["ctrl", "z"])
            return CommandResult.success(intent=intent, message="Undid")
        elif name == "REDO":
            self.input_injector.key_combination(["ctrl", "y"])
            return CommandResult.success(intent=intent, message="Redid")
        elif name == "KEY_COMBINATION":
            keys = intent.slots.get("keys", [])
            if keys:
                self.input_injector.key_combination(keys)
                return CommandResult.success(intent=intent, message=f"Pressed chord: {'+'.join(keys)}")
            return CommandResult.no_match(raw_text=intent.raw_text, message="Empty chord keys")
        elif name == "KEY_REPEAT":
            k = intent.slots.get("key", "")
            cnt = min(int(intent.slots.get("count", 1)), 50)
            for _ in range(cnt):
                self.input_injector.key_press(k)
            return CommandResult.success(intent=intent, message=f"Pressed {k} {cnt} times")
        elif name == "DRILL_DOWN_GRID":
            cell = int(intent.slots.get("cell", 1))
            self.overlay_service.drill_down_grid(cell)
            return CommandResult.success(intent=intent, message=f"Drilled down into cell {cell}")
        elif name == "UNDO_GRID":
            self.overlay_service.undo_grid()
            return CommandResult.success(intent=intent, message="Stepped back in grid")

        return CommandResult.no_match(raw_text=intent.raw_text, message=f"Unhandled intent: {name}")

    def execute_intent(self, intent: Intent) -> CommandResult:
        """Alias for dispatch_intent."""
        return self.dispatch_intent(intent)

    def _handle_show_numbers(self, intent: Intent, continuous: bool = False) -> CommandResult:
        elements = self.element_provider.discover_elements()
        self.overlay_service.show_numbers(elements, continuous=continuous)
        mode_text = f"Labeled {len(elements)} items (Continuous)" if continuous else f"Labeled {len(elements)} items"
        self.overlay_service.update_hud(mode=self.mode, text=mode_text)

        # Dynamic grammar loop: Push visible numbers (words + digits) & names to speech engine
        grammar_phrases = ["show numbers", "hide numbers", "show numbers continuously", "show grid", "hide grid"]
        max_num = max(25, len(elements))
        for num_i in range(1, max_num + 1):
            words = NumberParser.number_to_words(num_i)
            grammar_phrases.append(str(num_i))
            grammar_phrases.append(words)
            grammar_phrases.append(f"click {num_i}")
            grammar_phrases.append(f"click {words}")

        for el in elements:
            if el.name:
                clean_name = el.name.lower().strip()
                if clean_name:
                    grammar_phrases.append(clean_name)
                    grammar_phrases.append(f"click {clean_name}")
        self.speech_engine.set_grammar(grammar_phrases)

        return CommandResult.success(
            intent=intent,
            message=f"Displayed {len(elements)} numbers",
            element_count=len(elements),
        )

    def _handle_hide_numbers(self, intent: Intent) -> CommandResult:
        self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text="Numbers Hidden")
        return CommandResult.success(intent=intent, message="Numbers hidden")

    def _handle_click_number(
        self, intent: Intent, button: MouseButton = MouseButton.LEFT, count: int = 1
    ) -> CommandResult:
        num = intent.slots.get("number")
        if num is None:
            return CommandResult.no_match(raw_text=intent.raw_text, message="Missing number slot")

        try:
            num = int(num)
        except (ValueError, TypeError):
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_ELEMENT_NOT_FOUND",
                message=f"Invalid element number {num}",
                matched_intent=intent,
            )

        # Screen grid active: a bare number drills in (or clicks when it can't drill further);
        # "click <n>" etc. act at the cell centre and the grid then disappears (Apple guide).
        if self.overlay_service.is_grid_visible():
            cell_total = getattr(self.overlay_service, "grid_cell_count", lambda: 9)()
            if not isinstance(cell_total, int):
                cell_total = 9
            if 1 <= num <= cell_total:
                bare = (intent.raw_text or "").strip().lower().split()
                is_bare = len(bare) <= 1 or bare[0] in ("grid",)
                can = getattr(self.overlay_service, "can_drill_grid", lambda n: False)(num)
                if is_bare and can and button == MouseButton.LEFT and count == 1:
                    self.overlay_service.drill_down_grid(num)
                    return CommandResult.success(intent=intent, message=f"Drilled into grid cell {num}")
                coords = self.overlay_service.get_grid_cell_center(num)
                if coords:
                    self.input_injector.click_at(coords[0], coords[1], button, count)
                    self.overlay_service.hide_grid()
                    return CommandResult.success(
                        intent=intent,
                        message=f"Clicked grid cell {num}",
                        details={"x": coords[0], "y": coords[1]},
                    )

        element = self.element_provider.get_element_by_id(num)
        if not element:
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_ELEMENT_NOT_FOUND",
                message=f"No labeled element with number {num}",
                matched_intent=intent,
                details={"element_id": num},
            )

        # Verify target window is still alive
        if isinstance(element.window_handle, int) and element.window_handle > 0 and user32 is not None:
            if not user32.IsWindow(element.window_handle):
                self.element_provider.invalidate_cache()
                return CommandResult(
                    status=CommandStatus.ELEMENT_GONE,
                    code="ERR_WINDOW_GONE",
                    message=f"Target window {element.window_handle} was closed or destroyed",
                    matched_intent=intent,
                    details={"element_id": num},
                )

        cx, cy = element.rect.center()
        self.input_injector.click_at(cx, cy, button=button, count=count)
        if not self.overlay_service.is_continuous_numbers():
            self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text=f"Clicked #{num} ({element.name})")

        return CommandResult.success(
            intent=intent,
            message=f"Clicked element #{num} at ({cx}, {cy})",
            clicked_element=element.name,
            coordinates=(cx, cy),
        )

    def _handle_long_press_number(self, intent: Intent) -> CommandResult:
        num = intent.slots.get("number")
        if num is None:
            return CommandResult.no_match(raw_text=intent.raw_text, message="Missing number slot")
        element = self.element_provider.get_element_by_id(int(num))
        if not element:
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_ELEMENT_NOT_FOUND",
                message=f"No labeled element with number {num}",
                matched_intent=intent,
                details={"element_id": num},
            )
        cx, cy = element.rect.center()
        self.input_injector.long_press_at(cx, cy, duration_s=1.0)
        if not self.overlay_service.is_continuous_numbers():
            self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text=f"Long pressed #{num} ({element.name})")
        return CommandResult.success(
            intent=intent,
            message=f"Long pressed #{num}",
            coordinates=(cx, cy),
        )

    def _handle_drag_number(self, intent: Intent) -> CommandResult:
        from_num = intent.slots.get("from_number")
        to_num = intent.slots.get("to_number")
        if from_num is None or to_num is None:
            return CommandResult.no_match(raw_text=intent.raw_text, message="Missing drag endpoints")
        el1 = self.element_provider.get_element_by_id(int(from_num))
        el2 = self.element_provider.get_element_by_id(int(to_num))
        if not el1 or not el2:
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_ELEMENT_NOT_FOUND",
                message=f"Could not find elements #{from_num} or #{to_num}",
                matched_intent=intent,
            )
        x1, y1 = el1.rect.center()
        x2, y2 = el2.rect.center()
        self.input_injector.drag_and_drop(x1, y1, x2, y2, duration_s=0.3)
        if not self.overlay_service.is_continuous_numbers():
            self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text=f"Dragged #{from_num} to #{to_num}")
        return CommandResult.success(
            intent=intent,
            message=f"Dragged #{from_num} to #{to_num}",
            coordinates=(x2, y2),
        )

    def _handle_click_name(self, intent: Intent) -> CommandResult:
        name = intent.slots.get("name", "")
        if not name:
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_ELEMENT_NOT_FOUND",
                message="Missing element name",
                matched_intent=intent,
            )

        cached = self.element_provider.get_all_cached_elements()
        matches = self.command_parser.fuzzy_match_element(name, cached)

        if not matches:
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_ELEMENT_NOT_FOUND",
                message=f"No element matching name '{name}' found",
                matched_intent=intent,
            )

        best_element, score = matches[0]

        # Verify target window is still alive
        if best_element.window_handle and not user32.IsWindow(best_element.window_handle):
            self.element_provider.invalidate_cache()
            return CommandResult(
                status=CommandStatus.ELEMENT_GONE,
                code="ERR_WINDOW_GONE",
                message=f"Target window {best_element.window_handle} was closed or destroyed",
                matched_intent=intent,
                details={"element_id": best_element.element_id},
            )

        cx, cy = best_element.rect.center()
        self.input_injector.click_at(cx, cy)
        if not self.overlay_service.is_continuous_numbers():
            self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text=f"Clicked '{best_element.name}'")

        return CommandResult.success(
            intent=intent,
            message=f"Clicked '{best_element.name}' (confidence={score})",
            clicked_element=best_element.name,
            coordinates=(cx, cy),
        )

    def _handle_show_window_numbers(self, intent: Intent) -> CommandResult:
        primary_hwnd = self.element_provider._find_active_target_window()
        elements = self.element_provider.discover_elements(window_handle=primary_hwnd)
        self.overlay_service.show_numbers(elements, continuous=False)
        self.overlay_service.update_hud(mode=self.mode, text=f"Labeled {len(elements)} window items")
        return CommandResult.success(
            intent=intent,
            message=f"Displayed {len(elements)} window numbers",
            element_count=len(elements),
        )

    def _handle_show_window_grid(self, intent: Intent) -> CommandResult:
        hwnd = self.element_provider._find_active_target_window()
        rect = wintypes.RECT()
        sub_rect = None
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            sub_rect = ScreenRect(rect.left, rect.top, max(1, rect.right - rect.left), max(1, rect.bottom - rect.top))
        self.overlay_service.show_grid(sub_rect=sub_rect)
        self.overlay_service.update_hud(mode=self.mode, text="Window Grid Visible")
        return CommandResult.success(intent=intent, message="Window grid displayed")

    def _handle_show_names(self, intent: Intent) -> CommandResult:
        elements = self.element_provider.discover_elements()
        self.overlay_service.show_names(elements)
        self.overlay_service.update_hud(mode=self.mode, text=f"Labeled {len(elements)} names")
        return CommandResult.success(
            intent=intent,
            message=f"Displayed {len(elements)} names",
            element_count=len(elements),
        )

    def _handle_hide_names(self, intent: Intent) -> CommandResult:
        self.overlay_service.hide_names()
        self.overlay_service.update_hud(mode=self.mode, text="Names Hidden")
        return CommandResult.success(intent=intent, message="Names hidden")

    def _handle_start_drag_number(self, intent: Intent) -> CommandResult:
        num = int(intent.slots.get("number", 1))
        element = self.element_provider.get_element_by_id(num)
        if element:
            pt = element.rect.center()
            self.input_injector.move_cursor(pt[0], pt[1])
            time.sleep(0.02)
            self.input_injector.mouse_down(MouseButton.LEFT)
            return CommandResult.success(intent=intent, message=f"Started drag from #{num}")
        return CommandResult(
            status=CommandStatus.ELEMENT_GONE,
            code="ERR_ELEMENT_NOT_FOUND",
            message=f"No labeled element with number {num}",
            matched_intent=intent,
        )

    def _handle_move_cursor(self, intent: Intent) -> CommandResult:
        direction = str(intent.slots.get("direction", "right")).lower()
        amount = int(intent.slots.get("amount", 50))
        dx, dy = 0, 0
        if direction == "up":
            dy = -amount
        elif direction == "down":
            dy = amount
        elif direction == "left":
            dx = -amount
        elif direction == "right":
            dx = amount
        self.input_injector.move_cursor_relative(dx, dy)
        return CommandResult.success(intent=intent, message=f"Moved cursor {direction} by {amount}px")

    def _record_result(self, res: CommandResult) -> None:
        self._last_result = res
        for cb in list(getattr(self, "result_listeners", [])):
            try:
                cb(res)
            except Exception:  # pragma: no cover
                pass
        self._history.append(res)
