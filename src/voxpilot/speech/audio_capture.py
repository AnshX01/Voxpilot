"""
VoxPilot Audio Capture Service & Deterministic FakeMic
Owned by: Speech-Engine
Implements: IAudioCaptureService
"""

import queue
import threading
import time
import wave
from typing import Optional, List, Callable
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

from voxpilot.contracts.dto import AudioChunk
from voxpilot.contracts.errors import AudioDeviceError

class LiveAudioCapture:
    """WASAPI real-time microphone capture streaming 16kHz mono audio chunks."""

    def __init__(self, sample_rate: int = 16000, chunk_duration_ms: int = 50) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
        self.is_running = False
        self._stream: Optional[object] = None
        self._queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=100)

    def start(self, device_id: Optional[int] = None) -> None:
        if self.is_running:
            return
        if sd is None:
            raise AudioDeviceError("sounddevice package not available for live WASAPI capture.")

        self.is_running = True

        def callback(indata, frames, time_info, status):
            if status:
                pass
            if indata.shape[1] > 1:
                mono = indata.mean(axis=1)
            else:
                mono = indata[:, 0]

            pcm_int16 = (mono * 32767.0).clip(-32768, 32767).astype(np.int16).tobytes()
            chunk = AudioChunk(
                data=pcm_int16,
                sample_rate=self.sample_rate,
                channels=1,
                timestamp_ms=time.time() * 1000,
            )
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                pass

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_size,
            device=device_id,
            callback=callback,
        )
        self._stream.start()

    def read_chunk(self, timeout: float = 0.5) -> Optional[AudioChunk]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        self.is_running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class FakeMic:
    """Deterministic simulated microphone playing back WAV files at real-time or accelerated rate."""

    def __init__(self, wav_path: str, chunk_duration_ms: int = 50, real_time: bool = False) -> None:
        self.wav_path = wav_path
        self.chunk_duration_ms = chunk_duration_ms
        self.real_time = real_time
        self.is_running = False
        self._queue: queue.Queue[AudioChunk] = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.is_running = True
        self._thread = threading.Thread(target=self._feed_worker, daemon=True)
        self._thread.start()

    def _feed_worker(self) -> None:
        with wave.open(self.wav_path, "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            frames_per_chunk = int(sample_rate * (self.chunk_duration_ms / 1000.0))

            while self.is_running:
                data = wf.readframes(frames_per_chunk)
                if not data:
                    break

                if channels > 1:
                    arr = np.frombuffer(data, dtype=np.int16).reshape(-1, channels)
                    data = arr.mean(axis=1).astype(np.int16).tobytes()

                chunk = AudioChunk(
                    data=data,
                    sample_rate=sample_rate,
                    channels=1,
                    timestamp_ms=time.time() * 1000,
                )
                self._queue.put(chunk)
                if self.real_time:
                    time.sleep(self.chunk_duration_ms / 1000.0)

    def read_chunk(self, timeout: float = 0.2) -> Optional[AudioChunk]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)
