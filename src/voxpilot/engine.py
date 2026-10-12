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

        self.speech_engine.subscribe(self._on_transcript)

    def start(self) -> None:
        self.is_running = True
        self.speech_engine.start()
        self.overlay_service.update_hud(mode=self.mode, text="Ready")

    def stop(self) -> None:
        self.is_running = False
        self.speech_engine.stop()
        self.overlay_service.hide_all()
        self.input_injector.release_all_modifiers()

    def process_text_command(self, phrase: str) -> CommandResult:
        """Direct injection of phrase (e.g. for testing, fake-mic, or CLI 'voxpilot say')."""
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

        return CommandResult.no_match(raw_text=intent.raw_text, message=f"Unhandled intent: {name}")

    def _handle_show_numbers(self, intent: Intent) -> CommandResult:
        elements = self.element_provider.discover_elements()
        self.overlay_service.show_numbers(elements)
        self.overlay_service.update_hud(mode=self.mode, text=f"Labeled {len(elements)} items")

        # Dynamic grammar loop: Push visible numbers (words + digits) & names to speech engine
        grammar_phrases = ["show numbers", "hide numbers", "show grid", "hide grid"]
        for el in elements:
            words = NumberParser.number_to_words(el.element_id)
            grammar_phrases.append(str(el.element_id))
            grammar_phrases.append(words)
            grammar_phrases.append(f"click {el.element_id}")
            grammar_phrases.append(f"click {words}")
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
        if element.window_handle and not user32.IsWindow(element.window_handle):
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
