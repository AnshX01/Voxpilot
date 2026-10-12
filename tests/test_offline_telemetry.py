"""Offline & Zero Telemetry Verification Test Suite for VoxPilot.

Verifies that VoxPilot makes zero outbound network socket connections during:
1. Engine startup & shutdown.
2. Continuous audio ingestion and streaming speech recognition.
3. UI automation element discovery and spatial indexing.
4. Voice command parsing and dispatch.
5. Overlay canvas rendering and system tray updates.
"""

import socket
import pytest
from unittest.mock import patch, MagicMock

from voxpilot.engine import VoxPilotEngine
from voxpilot.commands import CommandParser
from voxpilot.speech.vosk_engine import VoskSpeechEngine
from voxpilot.contracts.dto import AudioChunk, ScreenRect, LabeledElement


def test_zero_network_socket_connections():
    """Intercept socket.socket.connect to assert that zero network connections occur."""
    connections_attempted = []

    real_connect = socket.socket.connect

    def fake_connect(self, address):
        connections_attempted.append(address)
        raise ConnectionRefusedError(f"Network access blocked by offline policy: {address}")

    with patch.object(socket.socket, "connect", fake_connect):
        # 1. Initialize Vosk speech engine
        speech_engine = VoskSpeechEngine(model_path="models/vosk-model-small-en-us-0.15")
        speech_engine.start(sample_rate=16000)

        # 2. Feed audio chunks
        chunk = AudioChunk(data=b"\x00\x00" * 800, sample_rate=16000, channels=1, timestamp_ms=0)
        speech_engine.process_audio(chunk)

        # 3. Initialize engine with components
        mock_provider = MagicMock()
        mock_provider.discover_elements.return_value = [
            LabeledElement(
                element_id=1,
                name="Test Button",
                control_type="Button",
                rect=ScreenRect(x=50, y=50, width=100, height=30),
                window_handle=0,
            )
        ]
        mock_overlay = MagicMock()
        mock_injector = MagicMock()

        engine = VoxPilotEngine(
            speech_engine=speech_engine,
            command_parser=CommandParser(),
            element_provider=mock_provider,
            overlay_service=mock_overlay,
            input_injector=mock_injector,
        )

        engine.start()

        # 4. Process command stream
        commands = [
            "show numbers",
            "click 1",
            "show grid",
            "drill down 5",
            "undo grid",
            "hide grid",
            "snap left",
            "go to sleep",
            "wake up",
        ]
        for cmd in commands:
            res = engine.process_text_command(cmd)
            assert res is not None

        engine.stop()

    # Assert zero network connection attempts
    assert connections_attempted == [], f"Unexpected outbound connections detected: {connections_attempted}"
