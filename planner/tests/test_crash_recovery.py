"""
Unit tests for COMPASS Crash & Restart Recovery Handler (§32).
Validates that tasks interrupted in non-terminal states are cleanly transitioned
to STOPPED and stale approvals are invalidated, with zero blind action resumption.
"""

import pytest

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.crash_recovery import CrashRecoveryHandler
from planner.human_approval import ApprovalState, human_approval_controller
from planner.models import ConfidenceLevel, Decision, PlannerActionType, RiskLevel


def test_interrupted_task_marked_stopped_on_startup():
    handler = CrashRecoveryHandler()
    t = task_service.create_task("Test task interrupted by crash")
    t_id = t["id"]
    task_service.transition_state(t_id, TaskState.PLANNING)
    task_service.transition_state(t_id, TaskState.VALIDATING)
    task_service.transition_state(t_id, TaskState.ACTING)

    recovered = handler.recover_interrupted_tasks()
    rec_ids = [r["task_id"] for r in recovered]
    assert t_id in rec_ids

    # Task must now be STOPPED
    updated_t = task_service.get_task(t_id)
    assert updated_t is not None
    assert updated_t["state"] == TaskState.STOPPED.value


def test_stale_approvals_invalidated_on_startup():
    handler = CrashRecoveryHandler()
    t = task_service.create_task("Test task with pending approval")
    t_id = t["id"]
    task_service.transition_state(t_id, TaskState.PLANNING)
    task_service.transition_state(t_id, TaskState.DECIDING)

    dec = Decision(
        decision_id="dec_crash_test",
        task_id=t_id,
        observation_id="obs_001",
        action=PlannerActionType.CLICK,
        target_description="Submit",
        confidence=ConfidenceLevel.HIGH,
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True,
        human_explanation="High risk action",
    )
    rec = human_approval_controller.create_approval_request(dec, window_hwnd=123)
    human_approval_controller.grant_approval(t_id, dec.decision_id)
    assert rec.state == ApprovalState.GRANTED

    # System crashes and restarts: run recovery
    handler.recover_interrupted_tasks()

    # Approval must be INVALIDATED
    appr = human_approval_controller.get_approval(t_id, dec.decision_id)
    assert appr is not None
    assert appr.state == ApprovalState.INVALIDATED
    assert (
        "restarted" in (appr.invalidation_reason or "").lower()
        or "interrupted" in (appr.invalidation_reason or "").lower()
    )


def test_completed_tasks_untouched_by_recovery():
    handler = CrashRecoveryHandler()
    t = task_service.create_task("Completed task")
    t_id = t["id"]
    task_service.transition_state(t_id, TaskState.PLANNING)
    task_service.transition_state(t_id, TaskState.VALIDATING)
    task_service.transition_state(t_id, TaskState.EXECUTING)
    task_service.transition_state(t_id, TaskState.VERIFYING)
    task_service.transition_state(t_id, TaskState.COMPLETED)

    recovered = handler.recover_interrupted_tasks()
    rec_ids = [r["task_id"] for r in recovered]
    assert t_id not in rec_ids

    task_after = task_service.get_task(t_id)
    assert task_after["state"] == TaskState.COMPLETED.value


def test_no_blind_action_resume_after_crash():
    handler = CrashRecoveryHandler()
    t = task_service.create_task("Interrupted task cannot be dispatched blindly")
    t_id = t["id"]
    task_service.transition_state(t_id, TaskState.PLANNING)
    task_service.transition_state(t_id, TaskState.VALIDATING)
    task_service.transition_state(t_id, TaskState.ACTING)

    handler.recover_interrupted_tasks()

    # Verify task state is STOPPED and cannot transition directly to ACTING or EXECUTING
    t_obj = task_service.get_task(t_id)
    assert t_obj["state"] == TaskState.STOPPED.value

    with pytest.raises(Exception):  # noqa: B017
        task_service.transition_state(t_id, TaskState.ACTING)
