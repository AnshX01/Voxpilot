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
    """WASAPI real-time microphone capture streaming 16kHz mono audio chunks with high-fidelity resampling."""

    def __init__(self, sample_rate: int = 16000, chunk_duration_ms: int = 50) -> None:
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
        self.is_running = False
        self._stream: Optional[object] = None
        self._queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=100)
        self.device_id: Optional[int] = None
        self.native_samplerate: int = sample_rate
        self.native_channels: int = 1

    def _find_best_input_device(self) -> Optional[int]:
        """Auto-detect optimal WASAPI input endpoint or return default."""
        if sd is None:
            return None
        try:
            devices = sd.query_devices()
            # First priority: Look for Windows WASAPI input device matching microphone
            wasapi_host_indices = [
                idx for idx, api in enumerate(sd.query_hostapis()) if "WASAPI" in api.get("name", "")
            ]
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0 and dev.get("hostapi") in wasapi_host_indices:
                    name = dev.get("name", "").lower()
                    if "microphone" in name or "mic" in name or "smart sound" in name:
                        return idx

            # Second priority: Any WASAPI input device
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0 and dev.get("hostapi") in wasapi_host_indices:
                    return idx

            # Fallback to default input
            def_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
            return def_in
        except Exception:
            return None

    def start(self, device_id: Optional[int] = None) -> None:
        if self.is_running:
            return
        if sd is None:
            raise AudioDeviceError("sounddevice package not available for live WASAPI capture.")

        chosen_dev = device_id if device_id is not None else self._find_best_input_device()
        self.device_id = chosen_dev

        # Determine native device parameters
        try:
            if chosen_dev is not None:
                dev_info = sd.query_devices(chosen_dev)
            else:
                dev_info = sd.query_devices(kind="input")
            self.native_samplerate = int(dev_info.get("default_samplerate", 48000))
            self.native_channels = min(int(dev_info.get("max_input_channels", 1)), 2)
        except Exception:
            self.native_samplerate = 48000
            self.native_channels = 1

        self.is_running = True
        native_sr = self.native_samplerate
        target_sr = self.sample_rate
        block_size = int(native_sr * (self.chunk_duration_ms / 1000.0))

        def callback(indata, frames, time_info, status):
            if indata.shape[1] > 1:
                mono = indata.mean(axis=1)
            else:
                mono = indata[:, 0]

            # Resample to 16kHz mono if device native sample rate differs
            if native_sr != target_sr:
                orig_len = len(mono)
                target_len = int(orig_len * (target_sr / float(native_sr)))
                if orig_len > 1 and target_len > 0:
                    mono = np.interp(
                        np.linspace(0, orig_len, target_len, endpoint=False),
                        np.arange(orig_len),
                        mono,
                    ).astype(np.float32)

            pcm_int16 = (mono * 32767.0).clip(-32768, 32767).astype(np.int16).tobytes()
            chunk = AudioChunk(
                data=pcm_int16,
                sample_rate=target_sr,
                channels=1,
                timestamp_ms=time.time() * 1000,
            )
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                pass

        self._stream = sd.InputStream(
            samplerate=self.native_samplerate,
            channels=self.native_channels,
            dtype="float32",
            blocksize=block_size,
            device=chosen_dev,
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
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
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
