"""
Phase 5 Crash & Component Failure Recovery Tests
(P5-REQ-017, P5-REQ-018)
Verifies safe degradation, failure classification, and recovery after:
- Target application crash or window closure
- Planner failure / malformed output
- Perception subsystem failure
- Verification failure
- Backend restart / CrashRecoveryHandler audit
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.app.database import db
from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from perception import uia_inspector
from planner.crash_recovery import crash_recovery_handler
from planner.execution_engine import ExecutionEngine
from planner.models import (
    FailureClassification,
    FailureState,
    PlannedAction,
    PlannerActionType,
    TaskPlan,
)
from planner.recovery_engine import recovery_engine
from planner.stale_guard import stale_guard


def test_target_application_crash_detection():
    """Detects when target application window closes or crashes during execution."""
    invalid_hwnd = 0xFFFFF1  # Dead HWND

    # Live UIA revalidation check on dead HWND
    target = {"name": "Document", "hwnd": invalid_hwnd, "automation_id": "txt_doc"}
    reval = uia_inspector.revalidate_element(target)
    assert reval["valid"] is False
    assert "no longer valid" in reval["reason"] or "invalid" in reval["reason"].lower()

    # Recovery engine classification
    diag = recovery_engine.diagnose_failure(
        cause=FailureClassification.APPLICATION_CRASHED,
        task_id="task_crash_01",
        original_goal="Edit document in Notepad",
        total_steps=3,
        failed_step_index=1,
        verified_step_indices=[0],
        details="Notepad process terminated unexpectedly",
    )
    assert diag.recommended_strategy == "HALT"
    assert diag.resulting_failure_state == FailureState.APPLICATION_CLOSED
    assert diag.preserve_completed_steps is True


def test_target_window_closed_between_steps():
    """Window closed between Step 1 and Step 2 halts execution rather than executing on desktop."""
    freshness = stale_guard.validate_freshness(
        observation_timestamp=time.time(),
        target_hwnd=0x999999,  # Non-existent HWND
        expected_window_title="Untitled - Notepad",
        is_sensitive=True,
    )
    assert freshness.is_fresh is False
    assert (
        "Target HWND" in freshness.stale_reason
        or "window" in freshness.stale_reason.lower()
    )


def test_planner_failure_fails_safely():
    """ExecutionEngine handles planner service exceptions cleanly without crash."""
    engine = ExecutionEngine()
    task = task_service.create_task("Test planner crash handling")
    tid = task["id"]

    mock_planner = MagicMock()
    mock_planner.create_plan.side_effect = RuntimeError(
        "OmniRoute upstream connection dropped"
    )
    engine.planner = mock_planner

    res = engine.run_task(tid)
    assert res["success"] is False
    assert res["status"] == "FAILED"
    assert "OmniRoute upstream connection dropped" in res["error"]

    # Verifies task is in terminal state FAILED
    t_rec = task_service.get_task(tid)
    assert t_rec["state"] == TaskState.FAILED.value


def test_perception_failure_fails_safely():
    """Perception subsystem handles UIA COM errors gracefully without raising unhandled crash."""
    with patch(
        "perception.uia_inspector._get_uia",
        side_effect=Exception("COM Automation CoInitialize error"),
    ):
        res = uia_inspector.get_element_tree(100)
        assert res["success"] is False
        assert res["error"] is not None


def test_verification_failure_fails_safely():
    """Verification failure gracefully traps exceptions and marks task FAILED cleanly."""
    engine = ExecutionEngine()
    task = task_service.create_task("Test verification crash handling")
    tid = task["id"]

    mock_plan = TaskPlan(
        task_id=tid,
        goal="Test",
        reasoning_summary="R",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.WAIT,
                target_description="Wait",
                expected_result="Wait done",
            )
        ],
    )
    mock_planner = MagicMock()
    mock_planner.create_plan.return_value = (True, mock_plan, "")
    engine.planner = mock_planner

    mock_verifier = MagicMock()
    mock_verifier.verify_action.side_effect = ValueError(
        "Unexpected snapshot structure"
    )
    engine.verifier = mock_verifier

    res = engine.run_task(tid)
    assert res["success"] is False
    assert res["status"] == "FAILED"

    t_rec = task_service.get_task(tid)
    assert t_rec["state"] == TaskState.FAILED.value


def test_backend_restart_recovery_audits_interrupted_tasks():
    """Backend restart detects lingering active tasks and transitions them to STOPPED cleanly."""
    # Create two tasks left in transitional states
    t1 = task_service.create_task("Interrupted task 1")
    t2 = task_service.create_task("Interrupted task 2")
    tid1 = t1["id"]
    tid2 = t2["id"]

    db.update_task_state(tid1, TaskState.ACTING.value, reason="Was executing click")
    db.update_task_state(
        tid2, TaskState.PLANNING.value, reason="Was waiting for planner"
    )

    recovered = crash_recovery_handler.recover_interrupted_tasks()
    recovered_ids = [r["task_id"] for r in recovered]

    assert tid1 in recovered_ids
    assert tid2 in recovered_ids

    # Both must now be STOPPED in database
    assert task_service.get_task(tid1)["state"] == TaskState.STOPPED.value
    assert task_service.get_task(tid2)["state"] == TaskState.STOPPED.value


def test_zero_blind_resumption_after_restart():
    """Interrupted tasks do not automatically dispatch new actions upon restart."""
    task = task_service.create_task("Interrupted task for restart test")
    tid = task["id"]
    db.update_task_state(tid, TaskState.ACTING.value, reason="Was executing click")

    crash_recovery_handler.recover_interrupted_tasks()

    t_rec = task_service.get_task(tid)
    assert t_rec["state"] == TaskState.STOPPED.value

    # Verifies task cannot transition to ACTING from STOPPED
    with pytest.raises(Exception):  # noqa: B017
        task_service.transition_state(
            tid, TaskState.ACTING, reason="Resuming after restart"
        )
