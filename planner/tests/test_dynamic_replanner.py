"""
Unit tests for DynamicReplanner (Phase 6, Capability E, §7, §9).
Verifies safe halt, state preservation, modal injection, and adapted plan synthesis.
"""

from planner.dynamic_replanner import DynamicReplanner
from planner.models import DecomposedPlan, StepStatus, TaskStep


def test_dynamic_replan_preserves_completed_steps():
    """Replanning preserves all verified COMPLETED steps and only resets uncompleted ones."""
    s1 = TaskStep(step_id="step_1", goal="Launch Notepad", status=StepStatus.COMPLETED)
    s2 = TaskStep(
        step_id="step_2",
        goal="Type text",
        status=StepStatus.FAILED,
        dependencies=["step_1"],
    )
    s3 = TaskStep(
        step_id="step_3",
        goal="Save file",
        status=StepStatus.PENDING,
        dependencies=["step_2"],
    )

    plan = DecomposedPlan(
        task_id="task_replan_1",
        goal="Notepad workflow",
        steps=[s1, s2, s3],
        dependencies={"step_1": [], "step_2": ["step_1"], "step_3": ["step_2"]},
    )

    replanner = DynamicReplanner()
    ok, new_plan, err = replanner.handle_replan_trigger(  # noqa: RUF059
        current_plan=plan,
        failed_step_id="step_2",
        reason="Target text editor not focused",
        live_window_info={"title": "Untitled - Notepad"},
        live_uia_tree=None,
    )

    assert ok is True
    assert new_plan is not None
    assert new_plan.version == 2
    # step_1 must remain COMPLETED
    assert new_plan.steps[0].step_id == "step_1"
    assert new_plan.steps[0].status == StepStatus.COMPLETED
    # step_2 must be reset to PENDING
    assert new_plan.steps[1].step_id == "step_2"
    assert new_plan.steps[1].status == StepStatus.PENDING


def test_dynamic_replan_injects_remedial_step_on_modal():
    """When a modal dialog is detected in live context, an acknowledgment step is injected."""
    s1 = TaskStep(step_id="step_1", goal="Step 1", status=StepStatus.COMPLETED)
    s2 = TaskStep(
        step_id="step_2",
        goal="Step 2",
        status=StepStatus.FAILED,
        dependencies=["step_1"],
    )

    plan = DecomposedPlan(
        task_id="task_replan_2",
        goal="Workflow with modal",
        steps=[s1, s2],
        dependencies={"step_1": [], "step_2": ["step_1"]},
    )

    replanner = DynamicReplanner()
    ok, new_plan, err = replanner.handle_replan_trigger(  # noqa: RUF059
        current_plan=plan,
        failed_step_id="step_2",
        reason="Unexpected prompt blocked action",
        live_window_info={"title": "Confirm Warning Dialog", "hwnd": 123},
        live_uia_tree={"name": "Confirm Warning Dialog", "control_type": "Dialog"},
    )

    assert ok is True
    assert len(new_plan.steps) == 3
    # Second step should be the remedial step
    assert "remedial_modal" in new_plan.steps[1].step_id
    assert "modal" in new_plan.steps[1].goal.lower()
