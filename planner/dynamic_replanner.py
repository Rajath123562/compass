"""
COMPASS Phase 6 — Dynamic Replanner
Handles unexpected UI shifts, modal dialogs, target movement, and partial step completions.
Safely halts execution, re-perceives state, preserves verified progress, and generates
validated adapted plans for remaining goals.
"""

from __future__ import annotations

import time
from typing import Any

from backend.app.logging_config import logger
from perception.context_analyzer import UIContextAnalyzer
from planner.loop_detector import LoopDetector
from planner.models import DecomposedPlan, RiskLevel, StepStatus, TaskStep
from planner.plan_validator import PlanValidator
from planner.task_decomposer import TaskDecomposer


class DynamicReplanner:
    """
    Coordinates safe, bounded dynamic replanning when the UI environment shifts.
    """

    def __init__(
        self,
        decomposer: TaskDecomposer | None = None,
        validator: PlanValidator | None = None,
        context_analyzer: UIContextAnalyzer | None = None,
        loop_detector: LoopDetector | None = None,
    ):
        self.validator = validator or PlanValidator()
        self.decomposer = decomposer or TaskDecomposer(validator=self.validator)
        self.context_analyzer = context_analyzer or UIContextAnalyzer()
        self.loop_detector = loop_detector or LoopDetector()

    def handle_replan_trigger(
        self,
        current_plan: DecomposedPlan,
        failed_step_id: str,
        reason: str,
        live_window_info: dict[str, Any] | None,
        live_uia_tree: dict[str, Any] | None,
    ) -> tuple[bool, DecomposedPlan | None, str | None]:
        """
        Execute the formal dynamic replanning protocol:
        1. Halt current execution.
        2. Contextual re-perception & modal detection.
        3. Check for infinite replanning loops.
        4. Partition into verified completed steps and remaining unfulfilled steps.
        5. Generate adapted remaining plan.
        6. Validate adapted plan.
        Returns (success, adapted_plan, error_message).
        """
        task_id = current_plan.task_id
        logger.warning(
            f"Dynamic replan triggered for task [{task_id}] at step [{failed_step_id}]: {reason}"
        )

        # Check non-repeatable safety boundary
        failed_step = next(
            (s for s in current_plan.steps if s.step_id == failed_step_id), None
        )
        if failed_step and not failed_step.repeatability:
            err = f"Non-repeatable step [{failed_step_id}] failed. Autonomous replan/retry prohibited."
            logger.warning(err)
            return False, None, err

        # 1. Analyze live context for unexpected modals or window changes
        ctx_analysis = self.context_analyzer.analyze_context(
            live_window_info, live_uia_tree
        )

        # 2. Partition steps: preserve all COMPLETED steps
        completed_steps = [
            s for s in current_plan.steps if s.status == StepStatus.COMPLETED
        ]
        uncompleted_steps = [
            s for s in current_plan.steps if s.status != StepStatus.COMPLETED
        ]

        logger.info(
            f"Task [{task_id}] partial completion: {len(completed_steps)} steps verified. {len(uncompleted_steps)} steps remaining."
        )

        # 3. Check for modal dialog requiring dismissal or acknowledgement
        additional_remedial_steps: list[TaskStep] = []
        if ctx_analysis.has_modal_dialog and ctx_analysis.active_dialog_title:
            logger.info(
                f"Modal dialog detected: '{ctx_analysis.active_dialog_title}'. Injecting acknowledgment step."
            )
            remedial_step = TaskStep(
                step_id=f"remedial_modal_{int(time.time())}",
                goal=f"Dismiss unexpected modal dialog: {ctx_analysis.active_dialog_title}",
                preconditions=[],
                target_description=f"Dialog button in {ctx_analysis.active_dialog_title}",
                risk_level=RiskLevel.MEDIUM,
                repeatability=False,
                expected_state_change="Modal dialog dismissed",
                verification_strategy="WINDOW_STATE",
                recovery_strategy="HALT",
                completion_condition={"dialog_closed": True},
                dependencies=[],
            )
            additional_remedial_steps.append(remedial_step)

        # 4. Synthesize remaining steps
        # Re-index remaining steps to ensure clean DAG continuity
        adapted_steps: list[TaskStep] = list(completed_steps)
        last_completed_id = completed_steps[-1].step_id if completed_steps else None

        # Add remedial steps if any
        for r_step in additional_remedial_steps:
            if last_completed_id:
                r_step.dependencies = [last_completed_id]
            adapted_steps.append(r_step)
            last_completed_id = r_step.step_id

        # Add remaining unfulfilled steps with updated dependency
        for u_step in uncompleted_steps:
            # Clone step to reset state for replanning
            new_step = u_step.model_copy(deep=True)
            new_step.status = StepStatus.PENDING
            new_step.error = None
            if last_completed_id and (
                not new_step.dependencies or failed_step_id in new_step.dependencies
            ):
                new_step.dependencies = [last_completed_id]
            adapted_steps.append(new_step)
            last_completed_id = new_step.step_id

        deps_map = {s.step_id: s.dependencies for s in adapted_steps}
        plan_hash = self.decomposer._hash_plan(adapted_steps)

        # 5. Check Loop Detector for replanning loops
        is_loop, loop_reason = self.loop_detector.record_replan(plan_hash)
        if is_loop:
            return False, None, f"Dynamic replanning terminated: {loop_reason}"

        # 6. Build adapted plan object
        adapted_plan = DecomposedPlan(
            task_id=task_id,
            goal=current_plan.goal,
            steps=adapted_steps,
            dependencies=deps_map,
            version=current_plan.version + 1,
            plan_hash=plan_hash,
            created_at=time.time(),
            max_execution_time_s=current_plan.max_execution_time_s,
        )

        # 7. Validate adapted plan
        is_valid, val_err = self.validator.validate_plan(adapted_plan)
        if not is_valid:
            return False, None, f"Adapted plan validation failed: {val_err}"

        return True, adapted_plan, None
