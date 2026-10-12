"""VoxPilot Chromium Native Messaging Host.

Implements Chromium Native Messaging framing protocol:
- 32-bit integer length prefix (native byte order)
- UTF-8 JSON payload
- Bidirectional communication between VoxPilot Engine and Browser Extension.
"""

from __future__ import annotations

import io
import json
import logging
import struct
import sys
import threading
import time
from typing import Any, BinaryIO, Callable, Dict, List, Optional

from ..contracts.dto import ActionType, LabeledElement, ScreenRect

logger = logging.getLogger("voxpilot.native_host")


def read_message(stream: BinaryIO) -> Optional[dict[str, Any]]:
    """Read a length-prefixed JSON message from a binary stream."""
    raw_length = stream.read(4)
    if len(raw_length) < 4:
        return None
    message_length = struct.unpack("@I", raw_length)[0]
    if message_length == 0:
        return None
    raw_payload = stream.read(message_length)
    if len(raw_payload) < message_length:
        return None
    try:
        decoded = raw_payload.decode("utf-8")
        return json.loads(decoded)
    except Exception as exc:
        logger.error("Failed to decode native messaging payload: %s", exc)
        return None


def send_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    """Encode and write a length-prefixed JSON message to a binary stream."""
    serialized = json.dumps(message, separators=(",", ":")).encode("utf-8")
    length_prefix = struct.pack("@I", len(serialized))
    stream.write(length_prefix)
    stream.write(serialized)
    stream.flush()


class NativeMessagingBridge:
    """Thread-safe bidirectional bridge between the browser extension and VoxPilot engine."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_dom_elements: List[LabeledElement] = []
        self._pending_response: Optional[dict[str, Any]] = None
        self._response_event = threading.Event()
        self._is_connected: bool = False

    def is_connected(self) -> bool:
        """Check if a browser extension instance has connected."""
        return self._is_connected

    def handle_incoming_message(self, msg: dict[str, Any]) -> None:
        """Process messages received from the browser extension background worker."""
        with self._lock:
            self._is_connected = True
            status = msg.get("status")
            if status == "ok" and "elements" in msg:
                raw_els = msg.get("elements", [])
                converted: List[LabeledElement] = []
                for idx, item in enumerate(raw_els, start=1):
                    rect = ScreenRect(
                        x=int(item.get("screen_x", 0)),
                        y=int(item.get("screen_y", 0)),
                        width=int(item.get("width", 10)),
                        height=int(item.get("height", 10)),
                    )
                    labeled = LabeledElement(
                        element_id=idx,
                        name=str(item.get("name", "")),
                        control_type=str(item.get("tag", "dom_element")),
                        rect=rect,
                        window_handle=0,
                        runtime_id=str(item.get("bridge_id", f"dom_{idx}")),
                        stability_key=f"dom_{item.get('tag')}_{item.get('name')[:15]}",
                        supported_actions=[ActionType.CLICK],
                    )
                    converted.append(labeled)
                self._last_dom_elements = converted

            self._pending_response = msg
            self._response_event.set()

    def get_cached_dom_elements(self) -> List[LabeledElement]:
        """Return the latest DOM elements collected from the browser tab."""
        with self._lock:
            return list(self._last_dom_elements)

    def request_elements_sync(
        self, out_stream: BinaryIO, in_stream: BinaryIO, timeout_seconds: float = 1.0
    ) -> List[LabeledElement]:
        """Send QUERY_DOM_ELEMENTS request and await response."""
        self._response_event.clear()
        req = {"action": "QUERY_DOM_ELEMENTS"}
        send_message(out_stream, req)

        # In a real environment, read_message would be called on reader thread
        # If in-stream is provided synchronously:
        start_t = time.perf_counter()
        while time.perf_counter() - start_t < timeout_seconds:
            msg = read_message(in_stream)
            if msg:
                self.handle_incoming_message(msg)
                break
            time.sleep(0.01)

        return self.get_cached_dom_elements()


def run_host_stdio() -> None:
    """Main loop for the Native Messaging Host running via Chrome/Edge stdio."""
    stdin_bin = sys.stdin.buffer
    stdout_bin = sys.stdout.buffer

    bridge = NativeMessagingBridge()

    while True:
        try:
            msg = read_message(stdin_bin)
            if msg is None:
                break
            bridge.handle_incoming_message(msg)
            # Echo heartbeat ack
            send_message(stdout_bin, {"status": "received", "timestamp": time.time()})
        except Exception as exc:
            logger.error("Native host exception: %s", exc)
            break


if __name__ == "__main__":
    run_host_stdio()
