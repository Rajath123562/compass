"""
COMPASS Phase 4 — Structured Decision Engine
Formulates machine-readable Decision models with schema validation,
deterministic risk & confidence fusion, and clear user-facing explanations.
Never permits model output to directly control the operating system.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from backend.app.logging_config import logger
from planner.confidence_engine import confidence_engine
from planner.models import Decision, PlannedAction, PlannerActionType, RiskLevel
from planner.risk_classifier import risk_classifier
from planner.security_guards import security_guard


class DecisionEngine:
    """
    Structured Decision Engine translating planned actions into strict, validated Decisions.
    Guarantees deterministic safety evaluation before any action can be considered.
    """

    def __init__(self):
        pass

    def formulate_decision(
        self,
        task_id: str,
        action: PlannedAction,
        target_element: dict[str, Any] | None = None,
        active_window: dict[str, Any] | None = None,
        observation_id: str = "",
        observation_age_ms: float = 0.0,
        visual_evidence: dict[str, Any] | None = None,
        original_goal: str = "",
    ) -> Decision:
        """
        Formulate a strict machine-readable Decision from a PlannedAction.
        """
        # 1. Deterministic Security Check (Arbitrary Command Rejection)
        sec_ok, sec_err = security_guard.validate_action_security(action)
        if not sec_ok:
            logger.error(f"DecisionEngine: Action security violation: {sec_err}")
            raise ValueError(f"Security validation failed: {sec_err}")

        # 2. Target Reference resolution
        target_ref = action.target_reference
        target_desc = action.target_description or ""
        target_name = (
            target_element.get("name")
            if target_element
            else (target_ref.name if target_ref else target_desc)
        ) or ""
        control_type = (
            target_element.get("control_type")
            if target_element
            else (target_ref.control_type if target_ref else "")
        ) or ""
        app_name = (
            active_window.get("title")
            if active_window
            else (target_ref.window_title if target_ref else "")
        ) or ""

        # 3. Evidence-Based Confidence Scoring
        conf_eval = confidence_engine.evaluate_confidence(
            target_ref=target_ref,
            element_snapshot=target_element,
            active_window=active_window,
            observation_age_ms=observation_age_ms,
            visual_evidence=visual_evidence,
        )

        # 4. Contextual Risk Classification
        risk_class = risk_classifier.classify_risk(
            action=action.action_type,
            target_name=target_name,
            target_control_type=control_type,
            parameters=action.parameters,
            application_name=app_name,
            window_title=app_name,
        )

        # 5. User-Facing Human Explanation
        explanation = self._generate_explanation(
            action, target_name, control_type, app_name
        )

        # 6. Action Idempotency
        # Non-repeatable if destructive or typing or key combo
        is_repeatable = action.action_type in [
            PlannerActionType.OBSERVE,
            PlannerActionType.HIGHLIGHT,
            PlannerActionType.WAIT,
            PlannerActionType.MOVE,
        ]
        if risk_class.risk_level == RiskLevel.HIGH:
            is_repeatable = False

        decision_id = f"dec_{uuid.uuid4().hex[:10]}"

        decision = Decision(
            decision_id=decision_id,
            task_id=task_id,
            observation_id=observation_id,
            timestamp=time.time(),
            action=action.action_type,
            target=target_ref,
            target_description=target_desc,
            parameters=action.parameters,
            confidence=conf_eval.level,
            confidence_score=conf_eval.score,
            confidence_signals=conf_eval.signals,
            risk_level=risk_class.risk_level,
            risk_reasons=risk_class.reasons,
            requires_confirmation=risk_class.requires_confirmation,
            human_explanation=explanation,
            expected_result=action.expected_result,
            verification_strategy=action.verification_condition.model_dump()
            if action.verification_condition
            else None,
            recovery_strategy={"strategy": "reobserve_and_replan"},
            is_repeatable=is_repeatable,
        )

        logger.info(
            f"DecisionEngine formulated [{decision_id}]: action='{action.action_type.value}', target='{target_name}', risk={risk_class.risk_level.value}, conf={conf_eval.level.value} ({conf_eval.score})"
        )
        return decision

    def _generate_explanation(
        self, action: PlannedAction, target_name: str, control_type: str, app_name: str
    ) -> str:
        """Generate clear, concise user-facing rationale."""
        atype = action.action_type
        target_label = target_name or "target element"

        if atype == PlannerActionType.TYPE:
            text = action.parameters.get("text", "")
            return (
                f"Type '{text}' into {target_label} in {app_name or 'the application'}."
            )
        elif atype == PlannerActionType.CLICK:
            return f"Click {target_label} to proceed with the task."
        elif atype == PlannerActionType.DOUBLE_CLICK:
            return f"Double-click {target_label} to open or activate it."
        elif atype == PlannerActionType.RIGHT_CLICK:
            return f"Right-click {target_label} to inspect options."
        elif atype in [PlannerActionType.KEY, PlannerActionType.KEY_PRESS]:
            key = action.parameters.get("key", "")
            return f"Press key '{key}' in {app_name or 'the application'}."
        elif atype == PlannerActionType.KEY_COMBINATION:
            combo = action.parameters.get("combination") or action.parameters.get(
                "keys", ""
            )
            return f"Send keyboard shortcut '{combo}'."
        elif atype == PlannerActionType.FOCUS:
            return f"Focus window or element '{target_label}'."
        elif atype == PlannerActionType.HIGHLIGHT:
            return f"Highlight {target_label} on screen."
        elif atype == PlannerActionType.WAIT:
            dur = action.parameters.get("duration_ms", 500)
            return f"Wait {dur}ms for interface to settle."
        elif atype == PlannerActionType.SCROLL:
            delta = action.parameters.get("delta", -120)
            dir_str = "down" if delta < 0 else "up"
            return f"Scroll mouse wheel {dir_str} on {target_label}."

        return f"Perform {atype.value} on {target_label}."


decision_engine = DecisionEngine()
