"""
Unit tests for Recovery Engine & Completed Step Preservation (Phase 4, Addendum §17, §18, Directive §17, §18).
"""

from planner.models import FailureState, PlannedAction, PlannerActionType, RecoveryCause
from planner.recovery_engine import recovery_engine


def test_completed_step_preservation_on_failure():
    """
    Directive §18 & Addendum §18: Step 1 ok, Step 2 ok, Step 3 fails ->
    Replanning starts from Step 3. Does NOT repeat Steps 1 and 2.
    """
    diagnosis = recovery_engine.diagnose_failure(
        cause=RecoveryCause.VERIFICATION_FAILED,
        task_id="task_test_123",
        original_goal="Format document",
        total_steps=5,
        failed_step_index=2,  # Step 3 (0-indexed 2)
        verified_step_indices=[0, 1],  # Steps 1 and 2 verified
        details="Button click did not toggle state",
    )

    assert diagnosis.preserve_completed_steps is True
    # Must resume from step index 2 (Step 3), NOT restart from 0
    assert diagnosis.resume_from_step_index == 2
    assert "Completed steps 1..2 remain preserved" in diagnosis.explanation


def test_user_intervention_overrides_stale_plan():
    """Directive §17 & Addendum §17: User intervention detected -> replan from current state."""
    diagnosis = recovery_engine.diagnose_failure(
        cause=RecoveryCause.USER_INTERVENTION,
        task_id="task_test_123",
        original_goal="Type text",
        total_steps=3,
        failed_step_index=1,
        verified_step_indices=[0],
        details="User closed dialog window",
    )

    assert diagnosis.recommended_strategy == "REOBSERVE_AND_REPLAN"
    assert diagnosis.preserve_completed_steps is True
    assert "User manual intervention detected" in diagnosis.explanation


def test_target_moved_diagnosis():
    diagnosis = recovery_engine.diagnose_failure(
        cause=RecoveryCause.TARGET_MOVED,
        task_id="task_test_123",
        original_goal="Click target",
        total_steps=2,
        failed_step_index=0,
        verified_step_indices=[],
    )
    assert diagnosis.recommended_strategy == "REOBSERVE_TARGET"


def test_adaptive_plan_merging():
    step1 = PlannedAction(
        action_type=PlannerActionType.FOCUS,
        target_description="Win",
        expected_result="Focused",
    )
    step2 = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Menu",
        expected_result="Opened",
    )
    new_step3 = PlannedAction(
        action_type=PlannerActionType.TYPE,
        target_description="Edit",
        parameters={"text": "Hi"},
        expected_result="Typed",
    )

    new_plan = recovery_engine.synthesize_adaptive_plan(
        task_id="task_test_123",
        original_goal="Type Hi",
        completed_steps=[step1, step2],
        remaining_steps=[],
        replan_steps=[new_step3],
        plan_version=1,
    )

    assert new_plan.plan_version == 2
    assert len(new_plan.steps) == 3
    assert new_plan.steps[0].action_type == PlannerActionType.FOCUS
    assert new_plan.steps[1].action_type == PlannerActionType.CLICK
    assert new_plan.steps[2].action_type == PlannerActionType.TYPE


def test_all_thirteen_failure_states_diagnosed():
    """
    Directive §13 & Addendum §13: Every single one of the 13 FailureState conditions
    must have a deterministic diagnosis, recommended strategy, and preserve verified progress.
    """
    all_states = [
        FailureState.AI_UNAVAILABLE,
        FailureState.PROVIDER_TIMEOUT,
        FailureState.INVALID_MODEL_OUTPUT,
        FailureState.TARGET_NOT_FOUND,
        FailureState.TARGET_CHANGED,
        FailureState.STALE_OBSERVATION,
        FailureState.ACTION_REJECTED,
        FailureState.ACTION_FAILED,
        FailureState.VERIFICATION_FAILED,
        FailureState.USER_CANCELLED,
        FailureState.APPLICATION_CLOSED,
        FailureState.SAFETY_BLOCKED,
        FailureState.BLOCKED,
    ]

    assert len(all_states) == 13, "Must test exactly 13 failure states"

    for state in all_states:
        diag = recovery_engine.diagnose_failure(
            cause=state,
            task_id="task_fail_13",
            original_goal="Complete 13-state validation",
            total_steps=4,
            failed_step_index=2,
            verified_step_indices=[0, 1],
            details=f"Test failure condition {state.value}",
        )
        assert diag.resulting_failure_state == state, (
            f"Failed state mapping for {state.value}"
        )
        assert diag.preserve_completed_steps is True
        assert len(diag.explanation) > 10
        assert diag.recommended_strategy in [
            "REOBSERVE_AND_REPLAN",
            "REOBSERVE_TARGET",
            "ASK_USER",
            "HALT",
            "RETRY_OR_REPLAN",
        ]
