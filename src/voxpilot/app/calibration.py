"""VoxPilot Audio Calibration & Onboarding Wizard.

Performs:
- Ambient noise floor measurement (RMS & peak dBFS)
- Microphone level and SNR health checks
- Calibration reading sentence verification (Word Error Rate check)
"""

from __future__ import annotations

import math
import time
from typing import Any, Optional
import numpy as np

from ..speech.audio_capture import LiveAudioCapture, FakeMic


class CalibrationWizard:
    """Automated microphone and acoustic calibration helper."""

    CALIBRATION_SENTENCE = "the quick brown fox jumps over the lazy dog"

    def __init__(self, capture_device: Optional[Any] = None) -> None:
        self.capture = capture_device or LiveAudioCapture(sample_rate=16000)

    def measure_noise_floor(self, duration_seconds: float = 1.0) -> dict[str, Any]:
        """Measure background noise floor over duration_seconds."""
        frames: list[bytes] = []

        def _collector(chunk: bytes) -> None:
            frames.append(chunk)

        try:
            self.capture.start(_collector)
            time.sleep(duration_seconds)
        finally:
            self.capture.stop()

        if not frames:
            return {
                "status": "error",
                "message": "No audio captured from microphone",
                "rms": 0.0,
                "dbfs": -100.0,
                "environment": "unknown",
            }

        raw_pcm = b"".join(frames)
        # 16-bit signed PCM
        samples = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0

        if len(samples) == 0:
            return {"status": "error", "message": "Zero audio samples", "rms": 0.0, "dbfs": -100.0}

        rms = float(np.sqrt(np.mean(samples**2)))
        dbfs = 20.0 * math.log10(rms) if rms > 1e-6 else -100.0

        # Assess environment acoustic health
        if dbfs < -45.0:
            env = "quiet"  # Ideal studio or quiet room
            quality = "excellent"
        elif dbfs < -30.0:
            env = "moderate"  # Normal office or home
            quality = "good"
        else:
            env = "noisy"  # High ambient noise, recommend headset mic
            quality = "degraded"

        return {
            "status": "ok",
            "sample_count": len(samples),
            "rms": round(rms, 5),
            "dbfs": round(dbfs, 2),
            "environment": env,
            "quality": quality,
        }

    @classmethod
    def verify_reading_sample(
        cls, spoken_text: str, target: Optional[str] = None
    ) -> dict[str, Any]:
        """Verify calibration sentence and calculate accuracy."""
        expected = (target or cls.CALIBRATION_SENTENCE).lower().split()
        actual = spoken_text.lower().split()

        if not expected:
            return {"accuracy": 1.0, "word_error_rate": 0.0}

        # Simple Levenshtein distance on words
        dp = [[0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
        for i in range(len(expected) + 1):
            dp[i][0] = i
        for j in range(len(actual) + 1):
            dp[0][j] = j

        for i in range(1, len(expected) + 1):
            for j in range(1, len(actual) + 1):
                if expected[i - 1] == actual[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

        distance = dp[len(expected)][len(actual)]
        wer = round(distance / len(expected), 3)
        accuracy = round(max(0.0, 1.0 - wer), 3)

        return {
            "expected": " ".join(expected),
            "actual": " ".join(actual),
            "distance": distance,
            "word_error_rate": wer,
            "accuracy": accuracy,
            "passed": accuracy >= 0.80,
        }
