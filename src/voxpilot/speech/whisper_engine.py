"""
VoxPilot Whisper Speech Engine Implementation
Owned by: Speech-Engine
Implements: ISpeechEngine (Dictation Mode)
"""

import time
from typing import Optional, List, Callable, Dict, Any
import numpy as np
import faster_whisper

from voxpilot.contracts.dto import AudioChunk, TranscriptEvent, EngineMode

class WhisperSpeechEngine:
    """High-accuracy offline speech engine for dictation mode."""

    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self._model = faster_whisper.WhisperModel(model_size, device=device, compute_type=compute_type)
        self._callbacks: List[Callable[[TranscriptEvent], None]] = []
        self._buffer: List[bytes] = []
        self._is_running = False
        self._sample_rate = 16000

    def start(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._buffer.clear()
        self._is_running = True

    def set_grammar(self, phrases: List[str]) -> None:
        pass

    def add_hotwords(self, words: List[str], boost: float = 1.5) -> None:
        pass

    def subscribe(self, callback: Callable[[TranscriptEvent], None]) -> None:
        self._callbacks.append(callback)

    def process_audio(self, chunk: AudioChunk) -> None:
        if not self._is_running:
            return
        self._buffer.append(chunk.data)

    def commit_buffer(self) -> Optional[TranscriptEvent]:
        """Transcribe accumulated audio buffer and dispatch final event."""
        if not self._buffer:
            return None

        raw_bytes = b"".join(self._buffer)
        self._buffer.clear()

        audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio_np) < 1600:
            return None

        t0 = time.perf_counter()
        segments, info = self._model.transcribe(audio_np, beam_size=1, language="en")
        text = " ".join([s.text for s in list(segments)]).strip()
        t1 = time.perf_counter()

        if text:
            event = TranscriptEvent(
                text=text,
                is_final=True,
                confidence=0.95,
                start_time_ms=t0 * 1000,
                end_time_ms=t1 * 1000,
                engine_mode=EngineMode.DICTATION,
            )
            for cb in self._callbacks:
                try:
                    cb(event)
                except Exception:
                    pass
            return event
        return None

    def stop(self) -> None:
        self._is_running = False
        self._buffer.clear()

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "engine": "faster-whisper",
            "model_size": self.model_size,
            "sample_rate": self._sample_rate,
        }
