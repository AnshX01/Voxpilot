"""Unit and integration tests for VoxPilot Chromium Browser Extension & Native Messaging Host."""

import io
import json
import os
import struct
import pytest

from voxpilot.native_host.host import (
    NativeMessagingBridge,
    read_message,
    send_message,
)


def test_native_messaging_framing_roundtrip() -> None:
    buf = io.BytesIO()
    payload = {
        "action": "QUERY_DOM_ELEMENTS",
        "tab_id": 101,
        "query": "interactive",
        "timestamp": 1234567.89,
    }

    send_message(buf, payload)
    buf.seek(0)

    # Inspect 4-byte header
    header_bytes = buf.read(4)
    expected_len = struct.unpack("@I", header_bytes)[0]
    buf.seek(0)

    result = read_message(buf)
    assert result is not None
    assert result == payload
    assert result["tab_id"] == 101


def test_native_messaging_empty_and_corrupt_stream() -> None:
    # Empty stream
    empty_buf = io.BytesIO()
    assert read_message(empty_buf) is None

    # Truncated length header (<4 bytes)
    short_buf = io.BytesIO(b"\x01\x02")
    assert read_message(short_buf) is None

    # Length header says 100 bytes, but stream has only 5 bytes
    incomplete_buf = io.BytesIO(struct.pack("@I", 100) + b"hello")
    assert read_message(incomplete_buf) is None


def test_native_messaging_bridge_dom_ingestion() -> None:
    bridge = NativeMessagingBridge()

    dom_payload = {
        "status": "ok",
        "tab_id": 42,
        "url": "https://example.com",
        "elements": [
            {
                "bridge_id": "voxdom_1",
                "tag": "button",
                "name": "Submit Order",
                "screen_x": 450,
                "screen_y": 300,
                "width": 120,
                "height": 40,
            },
            {
                "bridge_id": "voxdom_2",
                "tag": "a",
                "name": "Privacy Policy",
                "screen_x": 450,
                "screen_y": 360,
                "width": 150,
                "height": 20,
            },
        ],
    }

    bridge.handle_incoming_message(dom_payload)
    assert bridge.is_connected() is True

    cached = bridge.get_cached_dom_elements()
    assert len(cached) == 2

    btn = cached[0]
    assert btn.element_id == 1
    assert btn.name == "Submit Order"
    assert btn.control_type == "button"
    assert btn.rect.x == 450
    assert btn.rect.y == 300
    assert btn.rect.width == 120
    assert btn.rect.height == 40

    link = cached[1]
    assert link.element_id == 2
    assert link.name == "Privacy Policy"
    assert link.control_type == "a"


def test_extension_manifest_validity() -> None:
    manifest_path = os.path.join("extensions", "chromium", "manifest.json")
    assert os.path.exists(manifest_path), "Extension manifest.json missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("manifest_version") == 3
    assert "nativeMessaging" in manifest.get("permissions", [])
    assert manifest.get("background", {}).get("service_worker") == "background.js"
    assert len(manifest.get("content_scripts", [])) > 0


def test_native_host_manifest_validity() -> None:
    host_manifest_path = os.path.join("src", "voxpilot", "native_host", "com.voxpilot.host.json")
    assert os.path.exists(host_manifest_path), "Native host manifest missing"

    with open(host_manifest_path, "r", encoding="utf-8") as f:
        host_manifest = json.load(f)

    assert host_manifest.get("name") == "com.voxpilot.host"
    assert host_manifest.get("type") == "stdio"
    assert len(host_manifest.get("allowed_origins", [])) > 0
