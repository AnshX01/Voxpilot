"""VoxPilot Application Layer Package."""

from typing import Any

__all__ = [
    "CalibrationWizard",
    "VoxPilotTrayIcon",
]


def __getattr__(name: str) -> Any:
    if name == "CalibrationWizard":
        from .calibration import CalibrationWizard

        return CalibrationWizard
    if name == "VoxPilotTrayIcon":
        from .tray import VoxPilotTrayIcon

        return VoxPilotTrayIcon
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
