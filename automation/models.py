"""
COMPASS Automation Models
Pydantic and dataclass models for action requests, results, and validation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    KEY = "key"
    FOCUS = "focus"
    LAUNCH_APP = "launch_app"
    OPEN_URL = "open_url"


class ExecutionMethod(str, Enum):
    UIA_INVOKE = "uia_invoke"  # IUIAutomation InvokePattern
    UIA_VALUE = "uia_value"  # IUIAutomation ValuePattern::SetValue
    UIA_FOCUS = "uia_focus"  # IUIAutomation SetFocus
    SENDINPUT = "sendinput"  # Win32 SendInput (validated fallback only)
    SUBPROCESS = "subprocess"  # Direct process spawn
    SHELL_EXECUTE = "shell_execute"  # Windows ShellExecute


@dataclass
class ValidationResult:
    ok: bool
    reason: str
    element_snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "reason": self.reason}


@dataclass
class ActionResult:
    action_type: str
    success: bool
    execution_method: str = ""
    target_name: str = ""
    target_control_type: str = ""
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    log_id: int | None = None  # ID in action_log table

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "success": self.success,
            "execution_method": self.execution_method,
            "target_name": self.target_name,
            "target_control_type": self.target_control_type,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "log_id": self.log_id,
        }


# Virtual Key Code reference (subset for Phase 2)
VK_CODES: dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "tab": 0x09,
    "backspace": 0x08,
    "delete": 0x2E,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "a": 0x41,
    "b": 0x42,
    "c": 0x43,
    "d": 0x44,
    "e": 0x45,
    "f": 0x46,
    "g": 0x47,
    "h": 0x48,
    "i": 0x49,
    "j": 0x4A,
    "k": 0x4B,
    "l": 0x4C,
    "m": 0x4D,
    "n": 0x4E,
    "o": 0x4F,
    "p": 0x50,
    "q": 0x51,
    "r": 0x52,
    "s": 0x53,
    "t": 0x54,
    "u": 0x55,
    "v": 0x56,
    "w": 0x57,
    "x": 0x58,
    "y": 0x59,
    "z": 0x5A,
}

# Keys that require explicit safety check before sending
DANGEROUS_KEY_SEQUENCES: list[str] = [
    "win",
    "f4",  # Alt+F4 is dangerous but individual F4 is not
    "delete",  # Note: individual delete is usually safe
]

# System-owned window class names that must never be targeted
PROTECTED_WINDOW_CLASSES: list[str] = [
    "Shell_TrayWnd",  # Windows Taskbar
    "WorkerW",  # Desktop
    "Progman",  # Program Manager / Desktop
    "DV2ControlHost",  # Windows Welcome screen
    "#32770",  # Requires extra validation (system dialogs)
]

# Maximum text length allowed via type action (safety bound)
MAX_TYPE_LENGTH = 10_000
