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

class VoskSpeechEngine:
    """Streaming, grammar-biased offline speech recognition engine."""

    def __init__(self, model_path: str = DEFAULT_MODEL_DIR) -> None:
        self.model_path = model_path
        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(f"Vosk model not found at {self.model_path}")
        self._model = vosk.Model(self.model_path)
        self._recognizer: Optional[vosk.KaldiRecognizer] = None
        self._callbacks: List[Callable[[TranscriptEvent], None]] = []
        self._is_running = False
        self._grammar_phrases: Optional[List[str]] = None
        self._sample_rate = 16000
        self._words_recognized = 0
        self._chunks_processed = 0

    def start(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._reinit_recognizer()
        self._is_running = True

    def _reinit_recognizer(self) -> None:
        if self._grammar_phrases:
            grammar_json = json.dumps(self._grammar_phrases + ["[unk]"])
            self._recognizer = vosk.KaldiRecognizer(self._model, self._sample_rate, grammar_json)
        else:
            self._recognizer = vosk.KaldiRecognizer(self._model, self._sample_rate)
        self._recognizer.SetWords(True)

    def set_grammar(self, phrases: List[str]) -> None:
        """Update grammar in real time to bias recognition toward on-screen elements and commands."""
        cleaned = []
        for p in phrases:
            c = p.lower().strip()
            if c:
                cleaned.append(c)
        self._grammar_phrases = cleaned
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
