"""
Final State Verification Suite: Proves ACTION SUCCESS != TASK SUCCESS.
Tests:
  1. Action succeeds at OS dispatcher level, but expected final state is absent in target UI:
     task must NOT become COMPLETED; must transition to BLOCKED.
  2. Action succeeds and final state is verified in target UI:
     task transitions to COMPLETED.
"""

from unittest.mock import MagicMock, patch

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.execution_engine import ExecutionEngine
from planner.models import (
    PlannedAction,
    PlannerActionType,
    TaskPlan,
    VerificationResult,
    VerificationStatus,
)


def test_action_success_does_not_equal_task_success_when_final_state_absent():
    """
    CRITICAL MANDATE: Action success != Task success.
    Even if the action execution succeeds at the OS level, if final-state verification
    fails (e.g. expected typed text was not found in the target UI), the task MUST NOT
    become COMPLETED. It must transition to BLOCKED.
    """
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Type 'SecretData' into Notepad")
    tid = task["id"]

    plan = TaskPlan(
        task_id=tid,
        goal="Type 'SecretData' into Notepad",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.TYPE,
                target_description="Text editor",
                expected_result="Typed 'SecretData'",
                parameters={"text": "SecretData"},
            )
        ],
    )
    mock_planner.create_plan.return_value = (True, plan, None)

    # Step-level verification passes (action dispatch was accepted)
    mock_verifier.verify_action.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED,
        details="Key strokes dispatched successfully.",
    )

    # BUT final-state verification FAILS: 'SecretData' not actually present in Notepad
    mock_verifier.verify_final_goal_state.return_value = VerificationResult(
        status=VerificationStatus.FAILED,
        details="Final-state verification failed: expected text 'SecretData' not found in target UI.",
        observed_state={"elements_count": 5, "window_title": "Untitled - Notepad"},
        expected_state={"text": "SecretData"},
    )

    with patch.object(
        engine,
        "_dispatch_single_action",
        return_value={"success": True, "action_type": "type"},
    ), patch(
        "planner.human_approval.human_approval_controller.should_require_approval",
        return_value=False,
    ):
        res = engine.run_task(tid)

    # Must NOT be COMPLETED
    assert res.get("success") is False, (
        "Task falsely declared success when final state was absent!"
    )
    assert res.get("status") == "BLOCKED"
    assert "Final-state verification failed" in res.get("error", "")

    final_task = task_service.get_task(tid)
    assert final_task["state"] != TaskState.COMPLETED.value
    assert final_task["state"] == TaskState.BLOCKED.value


def test_action_success_with_verified_final_state_completes_task():
    """Verify that when both action succeeds AND final-state is verified with UI evidence, task completes."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Type 'VerifiedData' into Notepad")
    tid = task["id"]

    plan = TaskPlan(
        task_id=tid,
        goal="Type 'VerifiedData' into Notepad",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.TYPE,
                target_description="Text editor",
                expected_result="Typed 'VerifiedData'",
                parameters={"text": "VerifiedData"},
            )
        ],
    )
    mock_planner.create_plan.return_value = (True, plan, None)
    mock_verifier.verify_action.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED, details="Action verified."
    )
    mock_verifier.verify_final_goal_state.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED,
        details="Final-state verified: typed text 'VerifiedData' verified present in UI.",
        evidence={"text_matched": "VerifiedData"},
    )

    with patch.object(
        engine,
        "_dispatch_single_action",
        return_value={"success": True, "action_type": "type"},
    ), patch(
        "planner.human_approval.human_approval_controller.should_require_approval",
        return_value=False,
    ):
        res = engine.run_task(tid)

    assert res.get("success") is True
    assert res.get("status") == "COMPLETED"
    final_task = task_service.get_task(tid)
    assert final_task["state"] == TaskState.COMPLETED.value
