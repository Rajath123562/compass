"""
COMPASS Phase 6 — Plan Validator
Validates structural integrity, parameter safety, DAG dependencies,
resource limits, and risk boundaries of multi-step plans before execution.
Exhaustively validates all PlannerActionType schemas (COMPASS-AUDIT-017).
"""

from __future__ import annotations

from typing import Any

from planner.dependency_manager import StepDependencyManager
from planner.models import (
    DecomposedPlan,
    PlannedAction,
    PlannerActionType,
    RiskLevel,
    TaskStep,
)


class PlanValidationError(ValueError):
    """Raised when a plan violates structural, dependency, or safety constraints."""


class PlanValidator:
    """
    Validates DecomposedPlan instances prior to execution.
    Rejects malformed, circular, unbounded, or unsafely classified plans.
    """

    DEFAULT_MAX_STEPS = 15
    DEFAULT_MAX_DURATION_S = 180.0
    CONSEQUENTIAL_KEYWORDS = [  # noqa: RUF012
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
        "purge",
        "buy",
        "purchase",
        "submit",
        "pay",
        "checkout",
    ]

    FORBIDDEN_PARAM_KEYS = {  # noqa: RUF012
        "cmd",
        "shell",
        "exec",
        "eval",
        "payload",
        "system",
        "powershell",
        "bash",
        "spawn",
    }

    def __init__(
        self,
        max_steps: int = DEFAULT_MAX_STEPS,
        max_duration_s: float = DEFAULT_MAX_DURATION_S,
    ):
        self.max_steps = max_steps
        self.max_duration_s = max_duration_s
        self.dep_manager = StepDependencyManager()

    def validate_plan(self, plan: DecomposedPlan) -> tuple[bool, str | None]:
        """
        Comprehensive pre-execution plan validation.
        Returns (is_valid, failure_reason).
        """
        if not plan:
            return False, "Plan is None or empty."

        if not plan.task_id or not plan.task_id.strip():
            return False, "Plan missing task_id."

        if not plan.goal or not plan.goal.strip():
            return False, "Plan missing goal objective."

        if not plan.steps:
            return False, "Plan contains zero executable steps."

        # 1. Step Count Limit
        if len(plan.steps) > self.max_steps:
            return (
                False,
                f"Plan contains {len(plan.steps)} steps, exceeding maximum limit of {self.max_steps}.",
            )

        # 2. Maximum Duration Limit
        if plan.max_execution_time_s > self.max_duration_s * 2:
            return (
                False,
                f"Plan max_execution_time_s ({plan.max_execution_time_s}) exceeds allowable threshold ({self.max_duration_s * 2}).",
            )

        # 3. DAG & Dependency Validation
        is_dag_valid, dag_err = self.dep_manager.validate_dag(plan.steps)
        if not is_dag_valid:
            return False, f"Dependency validation failed: {dag_err}"

        # 4. Individual Step Validation
        for idx, step in enumerate(plan.steps):
            step_valid, step_err = self._validate_step(step, idx)
            if not step_valid:
                return False, f"Step '{step.step_id}' validation failed: {step_err}"

        return True, None

    def _validate_step(self, step: TaskStep, index: int) -> tuple[bool, str | None]:
        """Validate an individual step's attributes and actions."""
        if not step.goal or not step.goal.strip():
            return False, "Step missing goal description."

        if not step.verification_strategy or not step.verification_strategy.strip():
            return False, "Step missing verification_strategy."

        # Check Consequential Action Risk Classification across both goal and action parameters
        lower_goal = step.goal.lower()
        contains_consequential = any(
            kw in lower_goal for kw in self.CONSEQUENTIAL_KEYWORDS
        )

        # Also inspect candidate actions for consequential operations
        for act in step.candidate_actions:
            act_text = (
                f"{act.target_description} {act.expected_result} {act.parameters}"
            ).lower()
            if any(kw in act_text for kw in self.CONSEQUENTIAL_KEYWORDS):
                contains_consequential = True
                break

        if contains_consequential:
            if step.risk_level not in [
                RiskLevel.HIGH,
                RiskLevel.CONSEQUENTIAL,
                RiskLevel.BLOCKED,
            ]:
                return (
                    False,
                    f"Action appears consequential ('{step.goal}') but risk_level is '{step.risk_level.value}'. Must be HIGH or CONSEQUENTIAL.",
                )
            if step.repeatability is True:
                return (
                    False,
                    f"Consequential step '{step.step_id}' cannot have repeatability=True.",
                )

        # Validate Candidate Actions if present
        for act in step.candidate_actions:
            act_valid, act_err = self._validate_action(act)
            if not act_valid:
                return False, act_err

        return True, None

    def _validate_action(self, action: PlannedAction) -> tuple[bool, str | None]:
        """
        Validate individual PlannedAction parameters and bounds.
        Exhaustive schema check for all PlannerActionType enums (COMPASS-AUDIT-017).
        """
        atype = action.action_type
        params = action.parameters or {}

        # 1. Prohibit dangerous injection keys
        forbidden = set(params.keys()) & self.FORBIDDEN_PARAM_KEYS
        if forbidden:
            return (
                False,
                f"Action parameters contain prohibited key(s): {', '.join(sorted(forbidden))}.",
            )

        # 2. Exhaustive action type checks
        if atype == PlannerActionType.TYPE:
            if "text" not in params:
                return False, "TYPE action requires 'text' parameter."
            if len(str(params["text"])) > 10000:
                return False, "Text length exceeds 10000 character limit."

        elif atype == PlannerActionType.WAIT:
            duration = params.get("duration_ms", 500)
            if (
                not isinstance(duration, (int, float))
                or duration < 0
                or duration > 10000
            ):
                return False, "WAIT duration must be between 0 and 10000 ms."

        elif atype in [PlannerActionType.KEY, PlannerActionType.KEY_PRESS]:
            if "key" not in params:
                return False, f"{atype.value} action requires 'key' parameter."
            if not isinstance(params["key"], str) or len(params["key"]) > 50:
                return False, "Invalid 'key' parameter length or format."

        elif atype == PlannerActionType.KEY_COMBINATION:
            keys = params.get("keys") or params.get("combination")
            if not keys:
                return (
                    False,
                    "KEY_COMBINATION action requires 'keys' list or 'combination' string.",
                )
            if isinstance(keys, list):
                if len(keys) > 6:
                    return False, "KEY_COMBINATION exceeds maximum 6 keys."
            elif not isinstance(keys, str) or len(keys) > 100:
                return False, "KEY_COMBINATION string invalid or too long."

        elif atype in [
            PlannerActionType.CLICK,
            PlannerActionType.DOUBLE_CLICK,
            PlannerActionType.RIGHT_CLICK,
        ]:
            if "button" in params and params["button"] not in (
                "left",
                "right",
                "middle",
            ):
                return False, f"Invalid mouse button: {params['button']}"
            if "x" in params and not isinstance(params["x"], (int, float)):
                return False, "Coordinate 'x' must be a numeric value."
            if "y" in params and not isinstance(params["y"], (int, float)):
                return False, "Coordinate 'y' must be a numeric value."

        elif atype == PlannerActionType.MOVE:
            if "x" in params and not isinstance(params["x"], (int, float)):
                return False, "Coordinate 'x' must be a numeric value."
            if "y" in params and not isinstance(params["y"], (int, float)):
                return False, "Coordinate 'y' must be a numeric value."

        elif atype == PlannerActionType.SCROLL:
            amount = params.get("amount", params.get("delta_y", params.get("delta_x", 0)))
            if not isinstance(amount, (int, float)):
                return False, "SCROLL amount/delta must be a numeric value."
            if abs(amount) > 50000:
                return False, "SCROLL amount exceeds allowable magnitude 50000."

        elif atype == PlannerActionType.HIGHLIGHT:
            dur = params.get("duration_ms", 1000)
            if not isinstance(dur, (int, float)) or dur < 0 or dur > 10000:
                return False, "HIGHLIGHT duration must be between 0 and 10000 ms."

        elif atype == PlannerActionType.OBSERVE:
            app = params.get("app")
            if app and (not isinstance(app, str) or len(app) > 255):
                return False, "OBSERVE 'app' parameter exceeds 255 characters or is invalid."

        elif atype == PlannerActionType.ASK_USER:
            q = params.get("question") or params.get("prompt")
            if not q or not isinstance(q, str) or len(q) > 2000:
                return False, "ASK_USER requires valid 'question' string under 2000 characters."

        elif atype == PlannerActionType.FOCUS:
            pass  # Focus parameters are validated against target element

        elif atype in [PlannerActionType.STOP, PlannerActionType.REPLAN, PlannerActionType.VERIFY]:
            pass  # Control actions have no mandatory parameters

        elif atype == PlannerActionType.LAUNCH_APP:
            app = (
                params.get("app")
                or params.get("app_name")
                or params.get("name")
                or action.target_description
            )
            if not app or not isinstance(app, str) or len(app) > 500:
                return False, "LAUNCH_APP requires valid application name or path."

        elif atype == PlannerActionType.OPEN_URL:
            url = params.get("url") or action.target_description
            if not url or not isinstance(url, str) or len(url) > 2000:
                return False, "OPEN_URL requires valid URL string under 2000 characters."

        else:
            return False, f"Unsupported action type: '{atype}'."

        return True, None
