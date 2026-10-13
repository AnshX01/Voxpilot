"""
VoxPilot Vosk Streaming Speech Engine Implementation
Owned by: Speech-Engine
Implements: ISpeechEngine
"""

import json
import os
import time
from typing import Optional, List, Callable, Dict, Any
import vosk

from voxpilot.contracts.dto import AudioChunk, TranscriptEvent, TranscriptWord, EngineMode
from voxpilot.contracts.errors import AudioDeviceError

DEFAULT_MODEL_DIR = "models/vosk-model-small-en-us-0.15"

BASE_COMMAND_VOCABULARY = [
    # Top-level control phrases
    "show numbers", "show number", "hide numbers", "hide number",
    "show numbers continuously", "numbers continuously", "keep numbers on", "show numbers permanently",
    "show names", "hide names", "show item names", "names on", "names off",
    "show grid", "hide grid", "screen grid", "window grid", "grid on", "grid off",
    "show commands", "what can i say",
    "wake up", "start listening", "go to sleep", "stop listening", "sleep",
    "command mode", "switch to command mode",
    "dictation mode", "switch to dictation mode", "start dictation", "stop dictation",
    "mute", "unmute",
    # Interaction actions
    "click", "double click", "triple click", "right click", "control click",
    "long press", "press and hold", "click and hold", "tap", "choose", "press",
    "drag", "to", "into", "move", "drop",
    "scroll up", "scroll down", "scroll left", "scroll right",
    "zoom in", "zoom out", "undo", "undo that", "scratch that", "redo",
    # Keypresses & text manipulation
    "press enter", "enter", "press escape", "escape", "cancel",
    "press tab", "tab", "press backspace", "backspace", "delete character", "delete last word",
    "copy", "copy that", "cut", "cut that", "paste", "paste that", "select all",
    # Window & system controls
    "close window", "close app", "minimize window", "minimize", "maximize window", "maximize", "restore window",
    "show desktop", "snap window left", "snap window right", "snap window up", "snap window down",
    "switch app", "switch window", "alt tab", "task view", "next desktop", "previous desktop",
    "page up", "page down",
    # Digits and numbers (words and common compounds)
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand",
    "show window numbers", "show window grid", "hide commands",
    "start drag", "release", "scroll top", "scroll bottom", "scroll page up", "scroll page down",
    "show", "hide", "numbers", "number", "names", "grid", "double", "triple",
    "right", "left", "up", "down", "mode", "drag", "press", "hold", "scroll",
    "wake", "sleep", "start", "stop", "listening", "window", "app", "desktop",
    "cursor", "mouse", "pixels", "top", "bottom", "release",
]


class VoskSpeechEngine:
    """Streaming, grammar-biased offline speech recognition engine."""

    def __init__(self, model_path: str = DEFAULT_MODEL_DIR, use_command_grammar: bool = True) -> None:
        self.model_path = model_path
        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(f"Vosk model not found at {self.model_path}")
        self._model = vosk.Model(self.model_path)
        self._recognizer: Optional[vosk.KaldiRecognizer] = None
        self._callbacks: List[Callable[[TranscriptEvent], None]] = []
        self._is_running = False
        self._use_command_grammar = use_command_grammar
        self._grammar_phrases: Optional[List[str]] = list(BASE_COMMAND_VOCABULARY) if use_command_grammar else None
        self._sample_rate = 16000
        # Open vocabulary by default: a closed command grammar turns every non-listed word into [unk],
        # which made live speech unrecognisable. Commands are matched by the parser on open transcripts.
        self._open_vocab = True
        self._words_recognized = 0
        self._chunks_processed = 0

    def start(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._reinit_recognizer()
        self._is_running = True

    def set_open_vocabulary(self, open_vocab: bool) -> None:
        """Dictation/Spelling/Swift need open vocabulary; Command mode uses the closed command grammar."""
        if getattr(self, "_open_vocab", False) == open_vocab:
            return
        self._open_vocab = open_vocab
        if self._is_running:
            self._reinit_recognizer()

    def _reinit_recognizer(self) -> None:
        if self._grammar_phrases and not getattr(self, "_open_vocab", False):
            # Construct distinct vocabulary with [unk] token for unconstrained non-command speech filtering
            vocab = sorted(list({p.lower().strip() for p in self._grammar_phrases if p.strip()}))
            grammar_json = json.dumps(vocab + ["[unk]"])
            self._recognizer = vosk.KaldiRecognizer(self._model, self._sample_rate, grammar_json)
        else:
            self._recognizer = vosk.KaldiRecognizer(self._model, self._sample_rate)
        self._recognizer.SetWords(True)

    def set_grammar(self, phrases: List[str]) -> None:
        """Update grammar in real time to bias recognition toward on-screen elements and commands."""
        base = list(BASE_COMMAND_VOCABULARY) if self._use_command_grammar else []
        combined = set(base)
        for p in phrases:
            c = p.lower().strip()
            if c:
                combined.add(c)
        self._grammar_phrases = sorted(list(combined))
        if self._is_running:
            self._reinit_recognizer()

    def add_hotwords(self, words: List[str], boost: float = 1.5) -> None:
        if self._grammar_phrases is not None:
            self._grammar_phrases.extend([w.lower().strip() for w in words])
            self._reinit_recognizer()

    def subscribe(self, callback: Callable[[TranscriptEvent], None]) -> None:
        self._callbacks.append(callback)

    def process_audio(self, chunk: AudioChunk) -> None:
        if not self._is_running or not self._recognizer:
            return

        self._chunks_processed += 1

        if self._recognizer.AcceptWaveform(chunk.data):
            res_str = self._recognizer.Result()
            res = json.loads(res_str)
            text = res.get("text", "").strip()
            if text:
                event = TranscriptEvent(
                    text=text,
                    is_final=True,
                    confidence=1.0,
                    start_time_ms=chunk.timestamp_ms,
                    end_time_ms=time.time() * 1000,
                    engine_mode=EngineMode.COMMAND,
                )
                self._dispatch(event)
        else:
            partial_str = self._recognizer.PartialResult()
            partial = json.loads(partial_str)
            p_text = partial.get("partial", "").strip()
            if p_text:
                event = TranscriptEvent(
                    text=p_text,
                    is_final=False,
                    confidence=0.85,
                    start_time_ms=chunk.timestamp_ms,
                    end_time_ms=time.time() * 1000,
                    engine_mode=EngineMode.COMMAND,
                )
                self._dispatch(event)

    def flush(self) -> None:
        """Flush final result at end of speech or endpoint."""
        if self._recognizer:
            res_str = self._recognizer.FinalResult()
            res = json.loads(res_str)
            text = res.get("text", "").strip()
            if text:
                event = TranscriptEvent(
                    text=text,
                    is_final=True,
                    confidence=1.0,
                    start_time_ms=0,
                    end_time_ms=time.time() * 1000,
                    engine_mode=EngineMode.COMMAND,
                )
                self._dispatch(event)

    def _dispatch(self, event: TranscriptEvent) -> None:
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def stop(self) -> None:
        self._is_running = False

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "engine": "vosk",
            "model_path": self.model_path,
            "chunks_processed": self._chunks_processed,
            "sample_rate": self._sample_rate,
            "has_custom_grammar": self._grammar_phrases is not None,
        }
