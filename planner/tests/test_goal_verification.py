"""
Unit tests for MultiStepVerifier (Phase 6, Capability J, §12, §15).
Verifies step-level state delta analysis and final holistic goal verification.
"""

from planner.models import DecomposedPlan, StepStatus, TaskStep, VerificationStatus
from planner.multi_step_verifier import MultiStepVerifier


def test_step_verification_window_title_match():
    """Step verification succeeds when window title contains expected substring."""
    msv = MultiStepVerifier()
    step = TaskStep(
        step_id="step_1",
        goal="Launch Notepad",
        verification_strategy="WINDOW_STATE",
        completion_condition={"window_title_contains": "Notepad"},
    )

    res = msv.verify_step(
        step=step,
        pre_state=None,
        post_state={"window": {"title": "Untitled - Notepad"}},
        action_type="observe",
    )

    assert res.status == VerificationStatus.VERIFIED
    assert "matches expected substring" in res.details


def test_step_verification_window_title_mismatch():
    """Step verification fails when window title does not match expected substring."""
    msv = MultiStepVerifier()
    step = TaskStep(
        step_id="step_1",
        goal="Launch Notepad",
        verification_strategy="WINDOW_STATE",
        completion_condition={"window_title_contains": "Notepad"},
    )

    res = msv.verify_step(
        step=step,
        pre_state=None,
        post_state={"window": {"title": "Calculator"}},
        action_type="observe",
    )

    assert res.status == VerificationStatus.FAILED


def test_step_verification_filesystem_file_exists(tmp_path):
    """Step verification succeeds when expected file exists on disk."""
    msv = MultiStepVerifier()
    test_file = tmp_path / "output.txt"
    test_file.write_text("Test content", encoding="utf-8")

    step = TaskStep(
        step_id="step_save",
        goal="Save document",
        verification_strategy="FILESYSTEM",
        completion_condition={"file_path": str(test_file)},
    )

    res = msv.verify_step(
        step=step, pre_state=None, post_state=None, action_type="key_press"
    )
    assert res.status == VerificationStatus.VERIFIED
    assert "exists on filesystem" in res.details


def test_final_goal_verification_all_steps_completed():
    """Final goal verification succeeds when all steps are COMPLETED."""
    msv = MultiStepVerifier()
    steps = [
        TaskStep(step_id="step_1", goal="A", status=StepStatus.COMPLETED),
        TaskStep(step_id="step_2", goal="B", status=StepStatus.COMPLETED),
    ]
    plan = DecomposedPlan(task_id="task_goal_1", goal="Goal 1", steps=steps)

    res = msv.verify_final_goal(plan, live_window={"title": "App"})
    assert res.status == VerificationStatus.VERIFIED


def test_final_goal_verification_uncompleted_steps_fail():
    """Final goal verification fails if any step remains uncompleted."""
    msv = MultiStepVerifier()
    steps = [
        TaskStep(step_id="step_1", goal="A", status=StepStatus.COMPLETED),
        TaskStep(step_id="step_2", goal="B", status=StepStatus.PENDING),
    ]
    plan = DecomposedPlan(task_id="task_goal_2", goal="Goal 2", steps=steps)

    res = msv.verify_final_goal(plan, live_window={"title": "App"})
    assert res.status == VerificationStatus.FAILED
    assert "remain uncompleted" in res.details
