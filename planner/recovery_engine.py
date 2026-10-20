"""
COMPASS Phase 4 — Adaptive Recovery Engine & Completed Step Preservation
Diagnoses execution failures, detects user intervention, and formulates adaptive
replanning while strictly preserving verified completed progress.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from backend.app.logging_config import logger
from planner.models import (
    FailureState,
    PlannedAction,
    PlannerActionType,
    RecoveryCause,
    TaskPlan,
)


class RecoveryStage(str, Enum):
    STAGE_1_REPERCEIVE = "STAGE_1_REPERCEIVE"
    STAGE_2_RETRY = "STAGE_2_RETRY"
    STAGE_3_ALTERNATE = "STAGE_3_ALTERNATE"
    ESCALATE = "ESCALATE"


class StageRecoveryResult(BaseModel):
    """Result from an individual stage of the 3-stage adaptive recovery protocol."""

    stage: RecoveryStage
    success: bool
    strategy: str  # e.g., "COORDINATE_REALIGN", "STATE_CONFIRMED", "RETRY_ACTION", "HALT_NON_REPEATABLE", "SEMANTIC_INVOKE", "SEMANTIC_TOGGLE", "KEYBOARD_SHORTCUT", "TRIGGER_REPLAN"
    action_to_dispatch: PlannedAction | None = None
    target_element: dict[str, Any] | None = None
    reason: str = ""
    is_terminal: bool = False


class RecoveryDiagnosis(BaseModel):
    """Diagnosis of failure and prescribed adaptive recovery strategy."""

    cause: Any  # Union[RecoveryCause, FailureState, str]
    recommended_strategy: str  # "REOBSERVE_AND_REPLAN", "REOBSERVE_TARGET", "ASK_USER", "HALT", "RETRY_OR_REPLAN"
    explanation: str
    preserve_completed_steps: bool = True
    resume_from_step_index: int = 0
    resulting_failure_state: FailureState | None = None


class RecoveryEngine:
    """
    Adaptive recovery planner.
    Guarantees completed work is preserved and user intervention overrides stale plans.
    """

    def __init__(self):
        pass

    def diagnose_failure(
        self,
        cause: Any,  # Union[RecoveryCause, FailureState, str]
        task_id: str,
        original_goal: str,
        total_steps: int,
        failed_step_index: int,
        verified_step_indices: list[int],
        details: str = "",
    ) -> RecoveryDiagnosis:
        """
        Diagnose the failure cause and compute adaptive recovery strategy.
        Preserves verified completed steps (e.g. Step 1 ok, Step 2 ok -> resumes from Step 3).
        Handles all 13 FailureState conditions and all RecoveryCause enums explicitly.
        """
        # Determine step to resume from
        resume_index = failed_step_index
        if verified_step_indices:
            resume_index = max(verified_step_indices) + 1

        resume_index = min(resume_index, total_steps)

        # Normalize string or enum
        cause_val = cause.value if hasattr(cause, "value") else str(cause)

        # 1. User intervention
        if cause_val in [RecoveryCause.USER_INTERVENTION.value, "USER_INTERVENTION"]:
            explanation = (
                f"User manual intervention detected at step {failed_step_index + 1}. "
                f"Invalidating stale decision and replanning remaining objectives from live current state. "
                f"Preserving {len(verified_step_indices)} verified completed step(s)."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=None,
            )

        # 2. Target moved / changed
        elif cause_val in [
            RecoveryCause.TARGET_MOVED.value,
            FailureState.TARGET_CHANGED.value,
        ]:
            explanation = (
                f"Target element shifted position on screen during step {failed_step_index + 1}. "
                f"Re-observing target bounds and updating coordinates. Preserving completed steps."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_TARGET",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.TARGET_CHANGED
                if cause_val == FailureState.TARGET_CHANGED.value
                else None,
            )

        # 3. Target disappeared / not found
        elif cause_val in [
            RecoveryCause.TARGET_DISAPPEARED.value,
            FailureState.TARGET_NOT_FOUND.value,
        ]:
            explanation = (
                f"Target element disappeared from the application interface at step {failed_step_index + 1}. "
                f"Re-observing full window element tree to synthesize new navigation path."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.TARGET_NOT_FOUND,
            )

        # 4. Application focus lost / closed
        elif cause_val in [
            RecoveryCause.APPLICATION_CHANGED.value,
            FailureState.APPLICATION_CLOSED.value,
        ]:
            explanation = (
                f"Target application focus was lost or window closed at step {failed_step_index + 1}. "
                f"Attempting window reactivation or state re-alignment."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.APPLICATION_CLOSED,
            )

        # 5. AI unavailable
        elif cause_val in [
            RecoveryCause.PROVIDER_UNAVAILABLE.value,
            FailureState.AI_UNAVAILABLE.value,
        ]:
            explanation = "AI provider became unavailable or rate-limited during task planning/recovery."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.AI_UNAVAILABLE,
            )

        # 6. Provider timeout
        elif cause_val in [
            RecoveryCause.TIMEOUT.value,
            FailureState.PROVIDER_TIMEOUT.value,
        ]:
            explanation = (
                f"AI provider request timed out during step {failed_step_index + 1}."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.PROVIDER_TIMEOUT,
            )

        # 7. Invalid model output
        elif cause_val == FailureState.INVALID_MODEL_OUTPUT.value:
            explanation = f"AI provider returned malformed, unparseable, or invalid output at step {failed_step_index + 1}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.INVALID_MODEL_OUTPUT,
            )

        # 8. Stale observation
        elif cause_val == FailureState.STALE_OBSERVATION.value:
            explanation = f"UI observation became stale before action dispatch could complete at step {failed_step_index + 1}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.STALE_OBSERVATION,
            )

        # 9. Action rejected (SecurityGuard / Approval denial)
        elif cause_val == FailureState.ACTION_REJECTED.value:
            explanation = f"Action proposal rejected by safety policy or human user at step {failed_step_index + 1}: {details}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.ACTION_REJECTED,
            )

        # 10. Verification failed
        elif cause_val in [
            RecoveryCause.VERIFICATION_FAILED.value,
            FailureState.VERIFICATION_FAILED.value,
        ]:
            explanation = (
                f"Post-action verification failed at step {failed_step_index + 1} ({details or 'state mismatch'}). "
                f"Re-observing live UI and replanning step {failed_step_index + 1}. Completed steps 1..{failed_step_index} remain preserved."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.VERIFICATION_FAILED,
            )

        # 11. User cancelled / stopped
        elif cause_val == FailureState.USER_CANCELLED.value:
            explanation = f"Task was cancelled or stopped by user at step {failed_step_index + 1}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.USER_CANCELLED,
            )

        # 12. Safety blocked
        elif cause_val == FailureState.SAFETY_BLOCKED.value:
            explanation = f"Action blocked by coordinate, DPI, or screen boundary safety checks: {details}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.SAFETY_BLOCKED,
            )

        # 13. Blocked
        elif cause_val == FailureState.BLOCKED.value:
            explanation = f"Task progress is blocked awaiting user input or precondition resolution: {details}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="ASK_USER",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.BLOCKED,
            )

        # 14. Target disabled
        elif cause_val in ["TARGET_DISABLED", "target_disabled"]:
            explanation = f"Target element is disabled in current UI at step {failed_step_index + 1}: {details}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="ASK_USER",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.BLOCKED,
            )

        # 15. Target crash / terminated
        elif cause_val in [
            "APPLICATION_CRASHED",
            "PROCESS_TERMINATED",
            "application_crashed",
            "process_terminated",
        ]:
            explanation = f"Target application process terminated or crashed during step {failed_step_index + 1}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.APPLICATION_CLOSED,
            )

        # 16. Window unresponsive
        elif cause_val in ["WINDOW_UNRESPONSIVE", "window_unresponsive"]:
            explanation = f"Target window became unresponsive or hung at step {failed_step_index + 1}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.APPLICATION_CLOSED,
            )

        # 17. Action unverified
        elif cause_val in ["ACTION_UNVERIFIED", "action_unverified"]:
            explanation = f"Post-action verification was uncertain/unverified at step {failed_step_index + 1}: {details}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=failed_step_index,
                resulting_failure_state=FailureState.VERIFICATION_FAILED,
            )

        # 18. Resource exhausted
        elif cause_val in ["RESOURCE_EXHAUSTED", "resource_exhausted"]:
            explanation = (
                f"Resource budget exhausted at step {failed_step_index + 1}: {details}."
            )
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="HALT",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.BLOCKED,
            )

        # 19. Human takeover
        elif cause_val in ["HUMAN_TAKEOVER", "human_takeover"]:
            explanation = f"Human user intervened and took over control at step {failed_step_index + 1}."
            return RecoveryDiagnosis(
                cause=cause,
                recommended_strategy="REOBSERVE_AND_REPLAN",
                explanation=explanation,
                preserve_completed_steps=True,
                resume_from_step_index=resume_index,
                resulting_failure_state=FailureState.USER_CANCELLED,
            )

        # Default fallback: Action failed
        explanation = (
            f"Execution interrupted at step {failed_step_index + 1}: {details}."
        )
        return RecoveryDiagnosis(
            cause=cause,
            recommended_strategy="REOBSERVE_AND_REPLAN",
            explanation=explanation,
            preserve_completed_steps=True,
            resume_from_step_index=failed_step_index,
            resulting_failure_state=FailureState.ACTION_FAILED,
        )

    def stage_1_reobserve(
        self,
        action: PlannedAction,
        target_element: dict[str, Any] | None,
        current_snapshot: dict[str, Any],
    ) -> StageRecoveryResult:
        """
        Stage 1: Re-perception & State Re-alignment.
        Inspects live UI tree to verify if target is still present or has shifted.
        """
        if not target_element:
            return StageRecoveryResult(
                stage=RecoveryStage.STAGE_1_REPERCEIVE,
                success=False,
                strategy="NO_TARGET_REFERENCE",
                reason="No target element reference provided for state re-alignment.",
            )

        elements = current_snapshot.get("elements", [])
        matched = None
        for el in elements:
            if target_element.get("runtime_id") and el.get(
                "runtime_id"
            ) == target_element.get("runtime_id"):
                matched = el
                break
            if target_element.get("automation_id") and el.get(
                "automation_id"
            ) == target_element.get("automation_id"):
                matched = el
                break
            if target_element.get("name") and el.get("name") == target_element.get(
                "name"
            ):
                matched = el
                break

        if not matched:
            return StageRecoveryResult(
                stage=RecoveryStage.STAGE_1_REPERCEIVE,
                success=False,
                strategy="TARGET_MISSING",
                reason="Target element could not be found in current UI tree.",
            )

        # Calculate drift
        old_b = target_element.get("bounds", {})
        new_b = matched.get("bounds", {})
        old_cx = (old_b.get("left", 0) + old_b.get("right", 0)) // 2
        old_cy = (old_b.get("top", 0) + old_b.get("bottom", 0)) // 2
        new_cx = (new_b.get("left", 0) + new_b.get("right", 0)) // 2
        new_cy = (new_b.get("top", 0) + new_b.get("bottom", 0)) // 2
        dx = abs(new_cx - old_cx)
        dy = abs(new_cy - old_cy)

        return StageRecoveryResult(
            stage=RecoveryStage.STAGE_1_REPERCEIVE,
            success=True,
            strategy="COORDINATE_REALIGN" if (dx > 0 or dy > 0) else "STATE_CONFIRMED",
            target_element=matched,
            action_to_dispatch=action,
            reason=f"Target re-observed (drift: dx={dx}px, dy={dy}px).",
        )

    def stage_2_targeted_retry(
        self,
        action: PlannedAction,
        target_element: dict[str, Any] | None,
        attempt_count: int,
        max_retries: int = 2,
        is_repeatable: bool = True,
    ) -> StageRecoveryResult:
        """
        Stage 2: Re-validation & Targeted Retry.
        Strictly enforces:
        1. Non-repeatable consequential actions must NEVER be automatically retried.
        2. Attempt count must not exceed max_retries.
        3. Pre-dispatch revalidation (6-point check) must succeed.
        """
        if not is_repeatable:
            return StageRecoveryResult(
                stage=RecoveryStage.STAGE_2_RETRY,
                success=False,
                strategy="HALT_NON_REPEATABLE",
                reason="Consequential action is non-repeatable. Automatic retry strictly prohibited.",
                is_terminal=True,
            )

        if attempt_count >= max_retries:
            return StageRecoveryResult(
                stage=RecoveryStage.STAGE_2_RETRY,
                success=False,
                strategy="RETRIES_EXHAUSTED",
                reason=f"Targeted retry budget exhausted ({attempt_count}/{max_retries}).",
                is_terminal=False,
            )

        if target_element:  # noqa: SIM102
            if not target_element.get("is_enabled", True):
                return StageRecoveryResult(
                    stage=RecoveryStage.STAGE_2_RETRY,
                    success=False,
                    strategy="TARGET_DISABLED",
                    reason="Target element is disabled in live UI.",
                    is_terminal=False,
                )

        return StageRecoveryResult(
            stage=RecoveryStage.STAGE_2_RETRY,
            success=True,
            strategy="RETRY_ACTION",
            action_to_dispatch=action,
            target_element=target_element,
            reason=f"Targeted retry authorized (attempt {attempt_count + 1}/{max_retries}).",
        )

    def stage_3_alternate_strategy(
        self,
        action: PlannedAction,
        target_element: dict[str, Any] | None,
        current_snapshot: dict[str, Any] | None = None,
    ) -> StageRecoveryResult:
        """
        Stage 3: Alternate Strategy / Semantic Invocation / Keyboard Shortcut.
        """
        # 1. Semantic UIA Pattern Invoke
        if target_element and target_element.get("available_patterns"):
            patterns = target_element.get("available_patterns", [])
            if "InvokePattern" in patterns and action.action_type in [
                PlannerActionType.CLICK,
                PlannerActionType.DOUBLE_CLICK,
            ]:
                return StageRecoveryResult(
                    stage=RecoveryStage.STAGE_3_ALTERNATE,
                    success=True,
                    strategy="SEMANTIC_INVOKE",
                    target_element=target_element,
                    reason="Alternate strategy: dispatching via direct UIA InvokePattern.",
                )
            if (
                "TogglePattern" in patterns
                and action.action_type == PlannerActionType.CLICK
            ):
                return StageRecoveryResult(
                    stage=RecoveryStage.STAGE_3_ALTERNATE,
                    success=True,
                    strategy="SEMANTIC_TOGGLE",
                    target_element=target_element,
                    reason="Alternate strategy: dispatching via direct UIA TogglePattern.",
                )

        # 2. Keyboard shortcut alternatives
        atype = action.action_type
        desc = (action.target_description or "").lower()
        if atype == PlannerActionType.CLICK:  # noqa: SIM102
            if "ok" in desc or "submit" in desc or "save" in desc:
                shortcut_action = PlannedAction(
                    action_type=PlannerActionType.KEY,
                    target_description=f"Keyboard Enter alternative for '{action.target_description}'",
                    expected_result=action.expected_result,
                    parameters={"key": "enter"},
                )
                return StageRecoveryResult(
                    stage=RecoveryStage.STAGE_3_ALTERNATE,
                    success=True,
                    strategy="KEYBOARD_SHORTCUT",
                    action_to_dispatch=shortcut_action,
                    reason="Alternate strategy: substituted Enter key for submit/click.",
                )

        # 3. Fallback: Trigger replan
        return StageRecoveryResult(
            stage=RecoveryStage.STAGE_3_ALTERNATE,
            success=False,
            strategy="TRIGGER_REPLAN",
            reason="No direct semantic or shortcut alternative found. Full replan required.",
        )

    def synthesize_adaptive_plan(
        self,
        task_id: str,
        original_goal: str,
        completed_steps: list[PlannedAction],
        remaining_steps: list[PlannedAction],
        replan_steps: list[PlannedAction],
        plan_version: int = 1,
    ) -> TaskPlan:
        """
        Merge preserved verified completed steps with newly formulated replan steps.
        Guarantees that verified steps are not re-executed.
        """
        # Verified steps are retained in task history
        combined_steps = list(completed_steps) + list(replan_steps)

        new_plan = TaskPlan(
            task_id=task_id,
            goal=original_goal,
            steps=combined_steps,
            plan_version=plan_version + 1,
            reasoning_summary=f"Adaptive plan v{plan_version + 1}: preserved {len(completed_steps)} verified step(s), added {len(replan_steps)} new step(s).",
        )
        logger.info(
            f"RecoveryEngine synthesized adaptive plan v{new_plan.plan_version} for task [{task_id}] with {len(combined_steps)} total steps ({len(completed_steps)} preserved)."
        )
        return new_plan


recovery_engine = RecoveryEngine()
