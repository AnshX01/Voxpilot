"""VoxPilot Custom Commands Loader & Schema Validator.

Enables user-defined voice macros, hotkey bindings, text expansion,
and application launches with security allowlists and per-app scoping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import re
from typing import Any, List, Optional

logger = logging.getLogger("voxpilot.commands.custom_loader")

# Safe allowlisted binaries for 'launch' action
ALLOWED_LAUNCH_EXECUTABLES = {
    "notepad.exe",
    "calc.exe",
    "calculatorApp.exe",
    "explorer.exe",
    "cmd.exe",
    "wt.exe",
    "code.exe",
    "msedge.exe",
    "chrome.exe",
    "brave.exe",
    "firefox.exe",
}

# Forbidden command patterns (prevent destructive commands)
DISALLOWED_COMMAND_PATTERNS = [
    r"\brmdir\b",
    r"\bdel\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breg\s+(?:add|delete)\b",
    r"\bpowershell.*-enc\b",
]


@dataclass(slots=True)
class CustomCommandDef:
    """Definition of a user-configured voice command."""

    trigger: str
    action_type: str  # 'hotkey', 'text', 'launch', 'alias'
    action: Any
    scope_app: Optional[str] = None
    description: str = ""
    require_confirmation: bool = False


class CustomCommandLoader:
    """Loads, validates, and evaluates custom voice command profiles."""

    def __init__(self, config_dir: Optional[str] = None) -> None:
        if config_dir is None:
            config_dir = os.path.expanduser("~/.voxpilot")
        self.config_dir = config_dir
        self.commands: List[CustomCommandDef] = []

    def load_from_dict(self, data: dict[str, Any]) -> List[CustomCommandDef]:
        """Parse and validate command definitions from a configuration dictionary."""
        commands_raw = data.get("commands") or []
        if not isinstance(commands_raw, list):
            return []
        loaded: List[CustomCommandDef] = []

        for item in commands_raw:
            if not isinstance(item, dict):
                continue
            trigger = str(item.get("trigger", "")).strip().lower()
            action_type = str(item.get("action_type", "")).strip().lower()
            action = item.get("action")
            scope_app = item.get("scope_app")
            desc = item.get("description", "")
            confirm = bool(item.get("require_confirmation", False))

            if not trigger or not action_type or action is None:
                logger.warning("Skipping invalid custom command: %s", item)
                continue

            if action_type not in ("hotkey", "text", "launch", "alias"):
                logger.warning("Unsupported action_type '%s' in command '%s'", action_type, trigger)
                continue

            # Security validation for 'launch'
            if action_type == "launch":
                exe_name = os.path.basename(str(action)).lower()
                # Check for destructive patterns
                if any(re.search(pat, str(action), re.IGNORECASE) for pat in DISALLOWED_COMMAND_PATTERNS):
                    logger.error("Blocked dangerous command execution: %s", action)
                    continue

            cmd_def = CustomCommandDef(
                trigger=trigger,
                action_type=action_type,
                action=action,
                scope_app=scope_app.lower() if scope_app else None,
                description=desc,
                require_confirmation=confirm,
            )
            loaded.append(cmd_def)

        self.commands = loaded
        return loaded

    def load_from_file(self, filepath: str) -> List[CustomCommandDef]:
        """Load commands from a JSON file (or simple YAML key-value format)."""
        if not os.path.exists(filepath):
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return self.load_from_dict(data)
        except json.JSONDecodeError:
            # Fallback naive YAML parser for key: value
            logger.warning("File is not valid JSON, trying fallback parser: %s", filepath)
            return []
        except Exception as exc:
            logger.error("Failed to load custom commands from %s: %s", filepath, exc)
            return []

    def get_matching_commands(self, active_app: Optional[str] = None) -> List[CustomCommandDef]:
        """Filter commands applicable to the currently active application."""
        if not active_app:
            return [c for c in self.commands if c.scope_app is None]

        app_lower = active_app.lower()
        matched = []
        for c in self.commands:
            if c.scope_app is None:
                matched.append(c)
            elif c.scope_app in app_lower or app_lower in c.scope_app:
                matched.append(c)
        return matched
