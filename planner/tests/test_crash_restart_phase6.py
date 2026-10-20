"""
COMPASS Phase 6 — Crash & Interruption Recovery Tests
Verifies robust recovery and terminal safety when target applications crash,
perception or planner services fail, or backend/SSE processes are interrupted.
"""

from unittest.mock import patch

from backend.app.services.task_service import task_service
from planner.execution_controller import MultiStepExecutionController
from planner.models import (
    DecomposedPlan,
    PlannedAction,
    PlannerActionType,
    TaskState,
    TaskStep,
)


def test_target_application_crash_handling():
    """Verify that if the target application crashes unexpectedly, execution safely terminates without hanging."""
    controller = MultiStepExecutionController()
    t = task_service.create_task("App Crash Recovery Test")
    tid = t["id"]

    plan = DecomposedPlan(
        task_id=tid,
        goal="Interact with crashing app",
        steps=[
            TaskStep(
                step_id="step_1",
                goal="Click crashing button",
                candidate_actions=[
                    PlannedAction(
                        action_type=PlannerActionType.CLICK,
                        target_description="Button that terminates process",
                        expected_result="Clicked",
                    )
                ],
                verification_strategy="UIA_PATTERN",
                completion_condition={"text_contains": "Never"},
                repeatability=False,
            )
        ],
    )

    with patch.object(controller.decomposer, "decompose", return_value=plan):  # noqa: SIM117
        # Simulate target application abruptly disappearing/crashing on dispatch
        with patch.object(
            controller,
            "_dispatch_step_action",
            return_value={
                "success": False,
                "error": "Application window closed unexpectedly",
            },
        ):
            res = controller.run_multistep_task(tid, "Interact with crashing app")

    assert res["success"] is False
    assert res["status"] in ["BLOCKED", "FAILED"]
    task = task_service.get_task(tid)
    assert task["state"] in [TaskState.BLOCKED.value, TaskState.FAILED.value]


def test_planner_failure_safe_halt():
    """Verify that an unhandled planner failure safely marks task as FAILED and releases locks."""
    controller = MultiStepExecutionController()
    t = task_service.create_task("Planner Crash Test")
    tid = t["id"]

    with patch.object(
        controller.decomposer,
        "decompose",
        side_effect=RuntimeError("AI Provider memory fault"),
    ):
        res = controller.run_multistep_task(tid, "Do complex task")

    assert res["success"] is False
    assert res["status"] == "FAILED"
    task = task_service.get_task(tid)
    assert task["state"] == TaskState.FAILED.value
    assert (
        "fault" in task.get("error", "").lower()
        or "fault" in res.get("error", "").lower()
    )


def test_perception_failure_safe_halt():
    """Verify that total UIA/Screen capture failure halts execution safely rather than guessing."""
    controller = MultiStepExecutionController()
    t = task_service.create_task("Perception Crash Test")
    tid = t["id"]

    s1 = TaskStep(
        step_id="step_1",
        goal="Inspect desktop element",
        candidate_actions=[
            PlannedAction(
                action_type=PlannerActionType.OBSERVE,
                target_description="Desktop element",
                expected_result="Observed",
            )
        ],
        verification_strategy="UIA_PATTERN",
        repeatability=False,
    )
    plan = DecomposedPlan(task_id=tid, goal="Inspect desktop element", steps=[s1])

    with patch.object(controller.decomposer, "decompose", return_value=plan), patch(
        "perception.uia_inspector.get_foreground_window",
        side_effect=OSError("UIA RPC Server unavailable"),
    ):
        res = controller.run_multistep_task(tid, "Inspect desktop element")

    assert res["success"] is False
    assert res["status"] in ["FAILED", "BLOCKED"]


def test_verification_failure_safe_halt():
    """Verify that a verification exception triggers recovery or safe termination."""
    controller = MultiStepExecutionController()
    t = task_service.create_task("Verification Fault Test")
    tid = t["id"]

    s1 = TaskStep(
        step_id="step_1",
        goal="Perform action with broken verifier",
        repeatability=False,
    )
    plan = DecomposedPlan(
        task_id=tid, goal="Perform action with broken verifier", steps=[s1]
    )

    with patch.object(controller.decomposer, "decompose", return_value=plan):  # noqa: SIM117
        with patch.object(
            controller.verifier,
            "verify_step",
            side_effect=Exception("Corrupt verification pipe"),
        ):
            res = controller.run_multistep_task(
                tid, "Perform action with broken verifier"
            )

    assert res["success"] is False
    assert res["status"] in ["FAILED", "BLOCKED"]
