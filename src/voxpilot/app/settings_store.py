"""Voice Control settings (the options on Apple's "Change Voice Control settings" page).

Persisted as JSON in %APPDATA%\\VoxPilot\\settings.json (or ~/.voxpilot/settings.json). Nothing is read or
written until `load()` / `save()` is called, so tests and the CLI never touch user files by accident.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

OVERLAY_CHOICES = ("None", "Item names", "Item numbers", "Numbered grid")
ACTION_TYPES = ("Insert text", "Press keyboard shortcut", "Open URL", "Open app")


def default_path() -> str:
    base = os.environ.get("VOXPILOT_SETTINGS_DIR") or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), "VoxPilot" if os.environ.get("APPDATA") else ".voxpilot"
    )
    return os.path.join(base, "settings.json")


@dataclass
class VoiceControlSettings:
    language: str = "English"
    microphone: str = "Automatic"          # "Automatic" or a device name
    show_hints: bool = True                 # "Show hints"
    play_sound: bool = False                # "Play sound when command is recognized"
    overlay: str = "None"                   # "Overlay": None / Item names / Item numbers / Numbered grid
    fade_overlay: bool = False              # "Fade overlay after inactivity"
    fade_after_seconds: int = 5
    fade_amount: float = 0.5                # how far the overlay dims (0..1)
    vocabulary: List[str] = field(default_factory=list)
    # custom commands: {"when_i_say": str, "action": one of ACTION_TYPES, "value": str}
    custom_commands: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceControlSettings":
        s = cls()
        for k, v in (data or {}).items():
            if hasattr(s, k):
                setattr(s, k, v)
        if s.overlay not in OVERLAY_CHOICES:
            s.overlay = "None"
        return s

    @classmethod
    def load(cls, path: str | None = None) -> "VoiceControlSettings":
        try:
            with open(path or default_path(), "r", encoding="utf-8") as fh:
                return cls.from_dict(json.load(fh))
        except (OSError, ValueError):
            return cls()

    def save(self, path: str | None = None) -> str:
        p = path or default_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())
        return p


def export_custom_commands(settings: VoiceControlSettings, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"voxpilot_custom_commands": settings.custom_commands}, fh, indent=2)


def import_custom_commands(settings: VoiceControlSettings, path: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    items = data.get("voxpilot_custom_commands", []) if isinstance(data, dict) else []
    n = 0
    for it in items:
        if isinstance(it, dict) and it.get("when_i_say") and it.get("action") in ACTION_TYPES:
            settings.custom_commands.append({"when_i_say": str(it["when_i_say"]), "action": it["action"],
                                             "value": str(it.get("value", ""))})
            n += 1
    return n
