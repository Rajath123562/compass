"""
COMPASS Phase 6 — Partial Completion & Step Preservation Tests
Verifies that multi-step tasks maintain verified completed progress upon intermediate failures,
avoid unnecessary repetition of completed actions, and resume/replan from the safest valid state.
"""

from planner.dependency_manager import StepDependencyManager
from planner.dynamic_replanner import DynamicReplanner
from planner.models import DecomposedPlan, RiskLevel, StepStatus, TaskStep


def test_partial_completion_preserves_verified_steps():
    """Verify that earlier completed steps are never rolled back or repeated on later failures."""
    replanner = DynamicReplanner()

    s1 = TaskStep(
        step_id="step_1", goal="Open application", status=StepStatus.COMPLETED
    )
    s2 = TaskStep(
        step_id="step_2",
        goal="Login to account",
        status=StepStatus.COMPLETED,
        dependencies=["step_1"],
    )
    s3 = TaskStep(
        step_id="step_3",
        goal="Click export button",
        status=StepStatus.FAILED,
        dependencies=["step_2"],
    )
    s4 = TaskStep(
        step_id="step_4",
        goal="Confirm download",
        status=StepStatus.PENDING,
        dependencies=["step_3"],
    )

    plan = DecomposedPlan(
        task_id="partial_test_1",
        goal="Export financial report",
        steps=[s1, s2, s3, s4],
        dependencies={
            "step_1": [],
            "step_2": ["step_1"],
            "step_3": ["step_2"],
            "step_4": ["step_3"],
        },
    )

    success, new_plan, err = replanner.handle_replan_trigger(  # noqa: RUF059
        current_plan=plan,
        failed_step_id="step_3",
        reason="Export button occluded by tooltip",
        live_window_info={"title": "Dashboard"},
        live_uia_tree=None,
    )

    assert success is True
    assert new_plan is not None
    assert new_plan.version > 1

    # Steps 1 and 2 must remain COMPLETED
    step_dict = {s.step_id: s for s in new_plan.steps}
    assert step_dict["step_1"].status == StepStatus.COMPLETED
    assert step_dict["step_2"].status == StepStatus.COMPLETED


def test_consequential_action_never_auto_repeated_in_recovery():
    """Consequential operations (e.g. payment, delete) must not be blindly re-executed during recovery."""
    replanner = DynamicReplanner()

    s1 = TaskStep(
        step_id="step_1",
        goal="Submit payment transaction",
        risk_level=RiskLevel.CONSEQUENTIAL,
        repeatability=False,
        status=StepStatus.FAILED,
    )

    plan = DecomposedPlan(
        task_id="consequential_test",
        goal="Execute purchase",
        steps=[s1],
        dependencies={"step_1": []},
    )

    # Recovery must reject auto-retry of non-repeatable consequential step
    success, new_plan, err = replanner.handle_replan_trigger(  # noqa: RUF059
        current_plan=plan,
        failed_step_id="step_1",
        reason="Network timeout after dispatch",
        live_window_info={"title": "Payment Portal"},
        live_uia_tree=None,
    )

    assert success is False
    assert "non-repeatable" in (err or "").lower() or "halted" in (err or "").lower()


def test_cascading_blocked_downstream_steps():
    """Verify that downstream steps are properly marked BLOCKED when an upstream dependency fails."""
    dep_mgr = StepDependencyManager()

    s1 = TaskStep(step_id="s1", goal="Initial step", status=StepStatus.COMPLETED)
    s2 = TaskStep(
        step_id="s2",
        goal="Failing prerequisite",
        status=StepStatus.FAILED,
        dependencies=["s1"],
    )
    s3 = TaskStep(
        step_id="s3",
        goal="Dependent step A",
        status=StepStatus.PENDING,
        dependencies=["s2"],
    )
    s4 = TaskStep(
        step_id="s4",
        goal="Dependent step B",
        status=StepStatus.PENDING,
        dependencies=["s3"],
    )
    s5 = TaskStep(
        step_id="s5",
        goal="Independent step",
        status=StepStatus.PENDING,
        dependencies=["s1"],
    )

    steps = dep_mgr.cascade_downstream_blocks([s1, s2, s3, s4, s5])
    step_map = {s.step_id: s for s in steps}

    assert step_map["s1"].status == StepStatus.COMPLETED
    assert step_map["s2"].status == StepStatus.FAILED
    assert step_map["s3"].status == StepStatus.BLOCKED
    assert step_map["s4"].status == StepStatus.BLOCKED
    # Independent branch depending only on s1 must remain PENDING
    assert step_map["s5"].status == StepStatus.PENDING
