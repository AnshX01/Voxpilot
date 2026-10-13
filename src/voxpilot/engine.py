"""
VoxPilot Core Engine & Dispatcher
Ties together Audio/FakeMic -> Speech Engine -> Command Parser -> Automation -> Overlay -> Input Injection.
"""

import ctypes
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
)
from voxpilot.speech import VoskSpeechEngine, LiveAudioCapture, FakeMic
from voxpilot.commands import CommandParser, NumberParser
from voxpilot.automation import UiaElementProvider
from voxpilot.overlay import OverlayService
from voxpilot.input import WindowsInputInjector

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

        self.mode = EngineMode.COMMAND
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

        logger.info(f"Final transcript: '{event.text}'")
        self.process_text_command(event.text)

    def dispatch_intent(self, intent: Intent) -> CommandResult:
        name = intent.name

        # When in SLEEP mode, block all intents except WAKE_UP
        if self.mode == EngineMode.SLEEP and name != "WAKE_UP":
            return CommandResult.blocked(
                reason=BlockedReason.SECURE_DESKTOP,
                message="VoxPilot is asleep. Say 'wake up' to resume listening.",
            )

        if name == "SHOW_NUMBERS":
            return self._handle_show_numbers(intent)
        elif name == "HIDE_NUMBERS":
            return self._handle_hide_numbers(intent)
        elif name == "CLICK_NUMBER":
            return self._handle_click_number(intent)
        elif name == "DOUBLE_CLICK_NUMBER":
            return self._handle_click_number(intent, count=2)
        elif name == "RIGHT_CLICK_NUMBER":
            return self._handle_click_number(intent, button=MouseButton.RIGHT)
        elif name == "CLICK_NAME":
            return self._handle_click_name(intent)
        elif name == "SHOW_GRID":
            self.overlay_service.show_grid()
            self.overlay_service.update_hud(mode=self.mode, text="Grid Visible")
            return CommandResult.success(intent=intent, message="Grid displayed")
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

    def _handle_show_numbers(self, intent: Intent) -> CommandResult:
        elements = self.element_provider.discover_elements()
        self.overlay_service.show_numbers(elements)
        self.overlay_service.update_hud(mode=self.mode, text=f"Labeled {len(elements)} items")

        # Dynamic grammar loop: Push visible numbers (words + digits) & names to speech engine
        grammar_phrases = ["show numbers", "hide numbers", "show grid", "hide grid"]
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

        # Check if screen grid is active and number is 1-9
        if self.overlay_service.is_grid_visible() and 1 <= num <= 9:
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
        self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text=f"Clicked #{num} ({element.name})")

        return CommandResult.success(
            intent=intent,
            message=f"Clicked element #{num} at ({cx}, {cy})",
            clicked_element=element.name,
            coordinates=(cx, cy),
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
        self.overlay_service.hide_numbers()
        self.overlay_service.update_hud(mode=self.mode, text=f"Clicked '{best_element.name}'")

        return CommandResult.success(
            intent=intent,
            message=f"Clicked '{best_element.name}' (confidence={score})",
            clicked_element=best_element.name,
            coordinates=(cx, cy),
        )

    def _record_result(self, res: CommandResult) -> None:
        self._last_result = res
        self._history.append(res)
