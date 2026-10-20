"""
COMPASS Phase 4 — Goal Understanding Engine
Analyzes natural language goals, extracts target applications, constraints,
desired final states, subtask decomposition, ambiguity flags, and baseline risk.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from backend.app.logging_config import logger
from planner.models import RiskLevel


class GoalUnderstandingResult(BaseModel):
    """Structured result of natural language goal understanding."""

    raw_goal: str
    objective: str
    target_application: str | None = None
    target_application_executable: str | None = None
    constraints: list[str] = Field(default_factory=list)
    desired_final_state: str = ""
    possible_subtasks: list[str] = Field(default_factory=list)
    safety_level: RiskLevel = RiskLevel.LOW
    is_ambiguous: bool = False
    clarification_question: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)


class GoalUnderstandingEngine:
    """
    Deterministic & rule-grounded natural language goal parser.
    Provides immediate decomposition and validation before UI perception and planning.
    """

    KNOWN_APPS = {  # noqa: RUF012
        "notepad": {"name": "Notepad", "exe": "notepad.exe", "window_hint": "Notepad"},
        "calculator": {
            "name": "Calculator",
            "exe": "calc.exe",
            "window_hint": "Calculator",
        },
        "calc": {"name": "Calculator", "exe": "calc.exe", "window_hint": "Calculator"},
        "wordpad": {"name": "WordPad", "exe": "wordpad.exe", "window_hint": "WordPad"},
        "paint": {"name": "Paint", "exe": "mspaint.exe", "window_hint": "Paint"},
        "blender": {"name": "Blender", "exe": "blender.exe", "window_hint": "Blender"},
        "explorer": {
            "name": "File Explorer",
            "exe": "explorer.exe",
            "window_hint": "File Explorer",
        },
        "chrome": {
            "name": "Google Chrome",
            "exe": "chrome.exe",
            "window_hint": "Chrome",
        },
        "edge": {"name": "Microsoft Edge", "exe": "msedge.exe", "window_hint": "Edge"},
        "settings": {
            "name": "Settings",
            "exe": "start ms-settings:",
            "window_hint": "Settings",
        },
        "terminal": {
            "name": "Windows Terminal",
            "exe": "wt.exe",
            "window_hint": "Terminal",
        },
        "powershell": {
            "name": "PowerShell",
            "exe": "powershell.exe",
            "window_hint": "PowerShell",
        },
        "cmd": {
            "name": "Command Prompt",
            "exe": "cmd.exe",
            "window_hint": "Command Prompt",
        },
        "code": {
            "name": "Visual Studio Code",
            "exe": "code.exe",
            "window_hint": "Visual Studio Code",
        },
        "vscode": {
            "name": "Visual Studio Code",
            "exe": "code.exe",
            "window_hint": "Visual Studio Code",
        },
    }

    HIGH_RISK_KEYWORDS = [  # noqa: RUF012
        "delete",
        "remove",
        "erase",
        "wipe",
        "format",
        "drop",
        "truncate",
        "destroy",
        "kill",
        "terminate",
        "overwrite",
        "shutdown",
        "reboot",
        "uninstall",
        "purge",
    ]

    AMBIGUOUS_PATTERNS = [  # noqa: RUF012
        r"^(do it|fix this|click something|help|go|run|start|open it|type something)$",
        r"^\s*$",
        r"^.{1,3}$",
    ]

    _AMBIGUOUS_COMPILED = [re.compile(p, re.IGNORECASE) for p in AMBIGUOUS_PATTERNS]  # noqa: RUF012
    _KNOWN_APP_COMPILED = {  # noqa: RUF012
        app_key: re.compile(rf"\b{re.escape(app_key)}\b", re.IGNORECASE)
        for app_key in KNOWN_APPS
    }
    _HIGH_RISK_COMPILED = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in HIGH_RISK_KEYWORDS) + r")\b",
        re.IGNORECASE,
    )

    def __init__(self):
        pass

    def understand_goal(self, goal: str) -> GoalUnderstandingResult:
        """
        Parse and understand user goal string.
        """
        raw_goal = (goal or "").strip()
        cleaned_lower = raw_goal.lower()

        # 1. Ambiguity Detection
        is_ambiguous = False
        clarification_question = None

        if len(raw_goal) < 4:
            is_ambiguous = True
            clarification_question = "The requested goal is too short or underspecified. Could you describe the specific application and action you want COMPASS to perform?"
        else:
            for pattern in self._AMBIGUOUS_COMPILED:
                if pattern.search(cleaned_lower):
                    is_ambiguous = True
                    clarification_question = f"Your goal '{raw_goal}' is ambiguous. Please specify which application you want to use and the exact step to take."
                    break

        # 2. Target Application Extraction
        detected_app = None
        detected_exe = None
        for app_key, app_re in self._KNOWN_APP_COMPILED.items():
            if app_re.search(cleaned_lower):
                app_info = self.KNOWN_APPS[app_key]
                detected_app = app_info["name"]
                detected_exe = app_info["exe"]
                break

        if not detected_app:
            try:
                from automation.app_discovery import get_app_discovery
                # Try finding app candidate from "open/launch/start X" or full goal
                open_match = re.search(
                    r"\b(?:open|launch|start|run)\s+([a-zA-Z0-9_\-\. ]+)",
                    raw_goal,
                    re.IGNORECASE,
                )
                candidate = (
                    open_match.group(1).strip() if open_match else cleaned_lower
                )
                candidate = re.split(
                    r"\b(?:and|to|then|with|for|in)\b", candidate, flags=re.IGNORECASE
                )[0].strip()
                discovered = get_app_discovery().discover_app(candidate)
                if discovered:
                    detected_app = discovered.display_name
                    detected_exe = discovered.path or discovered.uri or discovered.key
            except Exception as ex:  # noqa: BLE001
                logger.debug(f"Dynamic app discovery error: {ex}")

        # 3. Risk Level Assessment
        safety_level = RiskLevel.LOW
        if self._HIGH_RISK_COMPILED.search(cleaned_lower):
            safety_level = RiskLevel.HIGH

        # 4. Objective & Desired Final State Extraction
        objective = raw_goal
        desired_final_state = f"Goal '{raw_goal}' completed and verified."
        if "type" in cleaned_lower:
            desired_final_state = "Expected text entered and visible in target editor."
        elif "click" in cleaned_lower or "open" in cleaned_lower:
            desired_final_state = "Target element activated or window opened."

        # 5. Constraints Extraction
        constraints = []
        if "without" in cleaned_lower:
            m = re.search(r"without\s+([^,.;]+)", raw_goal, re.IGNORECASE)
            if m:
                constraints.append(f"Do not {m.group(1).strip()}")
        if "save as" in cleaned_lower:
            m = re.search(r"save as\s+([^\s,.;]+)", raw_goal, re.IGNORECASE)
            if m:
                constraints.append(f"Save filename as {m.group(1).strip()}")

        # 6. Possible Subtasks Decomposition
        possible_subtasks = []
        if detected_app:
            possible_subtasks.append(f"Locate and focus {detected_app} window")
        else:
            possible_subtasks.append("Observe current desktop screen and active window")

        if "type" in cleaned_lower:
            possible_subtasks.append("Identify editable text area")
            possible_subtasks.append("Input requested text into target")
        elif "click" in cleaned_lower:
            possible_subtasks.append("Locate target button or interactive element")
            possible_subtasks.append("Click target element")
        else:
            possible_subtasks.append("Formulate plan steps based on active UI state")

        possible_subtasks.append("Verify final UI state satisfies objective")

        # 7. Required Capabilities
        capabilities = ["window_focus"]
        if (
            "type" in cleaned_lower
            or "write" in cleaned_lower
            or "enter" in cleaned_lower
        ):
            capabilities.extend(["text_input", "keyboard"])
        if "click" in cleaned_lower or "press" in cleaned_lower:
            capabilities.append("click")
        if "scroll" in cleaned_lower:
            capabilities.append("scroll")
        if not capabilities:
            capabilities = ["observe", "click"]

        result = GoalUnderstandingResult(
            raw_goal=raw_goal,
            objective=objective,
            target_application=detected_app,
            target_application_executable=detected_exe,
            constraints=constraints,
            desired_final_state=desired_final_state,
            possible_subtasks=possible_subtasks,
            safety_level=safety_level,
            is_ambiguous=is_ambiguous,
            clarification_question=clarification_question,
            required_capabilities=list(set(capabilities)),
        )
        logger.info(
            f"GoalUnderstandingEngine parsed goal '{raw_goal}': app={detected_app}, risk={safety_level.value}, ambiguous={is_ambiguous}"
        )
        return result


goal_understanding_engine = GoalUnderstandingEngine()
