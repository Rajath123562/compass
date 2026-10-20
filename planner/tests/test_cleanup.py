"""
Phase 5 Resource Cleanup Tests
(P5-REQ-014, P5-REQ-015, P5-REQ-016)
Tests resource and state cleanup across all 8 lifecycle terminal conditions:
1. Successful task
2. Failed task
3. Cancelled task (STOP)
4. Timeout
5. Recovery exhaustion
6. Application crash
7. Planner failure
8. AI unavailable
"""

import pytest

from backend.app.database import db
from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.circuit_breaker import ai_circuit_breaker
from planner.execution_engine import ExecutionEngine
from planner.human_approval import human_approval_controller
from planner.models import (
    ConfidenceLevel,
    Decision,
    PlannerActionType,
    RiskLevel,
    TaskPlan,
)


@pytest.fixture
def clean_engine():
    """Returns a fresh ExecutionEngine with clean database state."""
    engine = ExecutionEngine()
    return engine


def test_cleanup_after_successful_task(clean_engine):
    """Scenario 1: Cleanup after successful task execution."""
    task = task_service.create_task("Open calculator and compute result")
    tid = task["id"]

    # Emulate active state
    clean_engine._active_plans[tid] = TaskPlan(
        task_id=tid, goal="Test", reasoning_summary="Test plan", steps=[]
    )
    db.update_task_state(
        tid, TaskState.COMPLETED.value, reason="Task finished successfully"
    )

    res = clean_engine.cleanup_task_resources(tid)
    assert res["had_active_plan"] is True
    assert tid not in clean_engine._active_plans

    # State remains COMPLETED
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.COMPLETED.value


def test_cleanup_after_failed_task(clean_engine):
    """Scenario 2: Cleanup after execution failure."""
    task = task_service.create_task("Click non-existent widget")
    tid = task["id"]

    clean_engine._active_plans[tid] = TaskPlan(
        task_id=tid, goal="Test", reasoning_summary="P", steps=[]
    )
    task_service.transition_state(
        tid, TaskState.FAILED, reason="Target control not found"
    )

    res = clean_engine.cleanup_task_resources(tid)  # noqa: F841
    assert tid not in clean_engine._active_plans
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value


def test_cleanup_after_cancelled_task_stop(clean_engine):
    """Scenario 3: Cleanup after user asserts STOP."""
    task = task_service.create_task("Long running sequence")
    tid = task["id"]

    clean_engine.stop_task(tid, reason="User clicked STOP")
    assert clean_engine.is_stopped(tid) is True

    res = clean_engine.cleanup_task_resources(tid)  # noqa: F841
    assert tid not in clean_engine._active_plans
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.STOPPED.value


def test_cleanup_after_confirmation_timeout(clean_engine):
    """Scenario 4: Cleanup after approval request timeout."""
    task = task_service.create_task("Delete file")
    tid = task["id"]

    dec = Decision(
        decision_id="dec_to_test",
        task_id=tid,
        action=PlannerActionType.CLICK,
        target_description="Delete File",
        confidence=ConfidenceLevel.HIGH,
        risk_level=RiskLevel.HIGH,
        human_explanation="Deleting test file",
        requires_confirmation=True,
        is_repeatable=False,
    )
    human_approval_controller.create_approval_request(
        decision=dec, window_hwnd=100, application_name="Explorer", timeout_seconds=0.1
    )

    clean_engine.cleanup_task_resources(tid)
    # Check that task approvals are cleaned
    cleaned = human_approval_controller.cleanup_task(tid)
    assert cleaned == 0  # Already cleaned by cleanup_task_resources


def test_cleanup_after_recovery_exhaustion(clean_engine):
    """Scenario 5: Cleanup after retries/recovery budget exhausted."""
    task = task_service.create_task("Retry flaky button")
    tid = task["id"]

    task_service.transition_state(
        tid, TaskState.FAILED, reason="Max recovery retries exhausted (3/3)"
    )
    res = clean_engine.cleanup_task_resources(tid)  # noqa: F841
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value


def test_cleanup_after_application_crash(clean_engine):
    """Scenario 6: Cleanup after target application window crashes."""
    task = task_service.create_task("Interact with unstable process")
    tid = task["id"]

    # Simulating transitional state when crash occurred
    db.update_task_state(tid, TaskState.ACTING.value, reason="Dispatching click")

    res = clean_engine.cleanup_task_resources(tid)
    assert res["terminal_state_enforced"] is True
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value  # Enforced terminal state


def test_cleanup_after_planner_failure(clean_engine):
    """Scenario 7: Cleanup after planner returns invalid schema."""
    task = task_service.create_task("Parse unparseable intent")
    tid = task["id"]

    db.update_task_state(tid, TaskState.PLANNING.value, reason="Waiting for AI plan")
    res = clean_engine.cleanup_task_resources(tid)
    assert res["terminal_state_enforced"] is True
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value


def test_cleanup_after_ai_unavailable(clean_engine):
    """Scenario 8: Cleanup when AI provider circuit breaker is OPEN."""
    task = task_service.create_task("Generate plan when AI is down")
    tid = task["id"]

    # Force circuit breaker open
    for _ in range(6):
        ai_circuit_breaker.record_failure()
    assert ai_circuit_breaker.can_execute() is False

    res = clean_engine.run_task(tid)
    assert res["success"] is False
    assert res["status"] == "FAILED"
    assert "circuit breaker is OPEN" in res["error"]

    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value
    assert tid not in clean_engine._active_plans

    # Reset circuit breaker
    ai_circuit_breaker.reset()


def test_cleanup_after_verification_failure(clean_engine):
    """Scenario 9: Cleanup after verification repeatedly fails."""
    task = task_service.create_task("Verify toggle state change")
    tid = task["id"]

    db.update_task_state(
        tid, TaskState.VERIFYING.value, reason="Checking state transition"
    )
    clean_engine._active_plans[tid] = TaskPlan(
        task_id=tid, goal="Verify", reasoning_summary="V", steps=[]
    )

    task_service.transition_state(tid, TaskState.FAILED, reason="Verification mismatch")
    res = clean_engine.cleanup_task_resources(tid)  # noqa: F841
    assert tid not in clean_engine._active_plans
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value


def test_cleanup_after_sse_interruption(clean_engine):
    """Scenario 10: Cleanup when client drops SSE connection mid-execution."""
    task = task_service.create_task("Long stream task")
    tid = task["id"]

    # Simulating disconnected client while engine was guiding
    db.update_task_state(tid, TaskState.GUIDING.value, reason="Streaming SSE events")
    res = clean_engine.cleanup_task_resources(tid)
    assert res["terminal_state_enforced"] is True
    t_after = task_service.get_task(tid)
    assert t_after["state"] == TaskState.FAILED.value  # Enforced terminal state


def test_cleanup_after_unexpected_exception(clean_engine):
    """Scenario 11: Cleanup after unhandled exception in background worker."""
    task = task_service.create_task("Fault injection task")
    tid = task["id"]

    db.update_task_state(tid, TaskState.EXECUTING.value, reason="Active execution")
    res = clean_engine.cleanup_task_resources(tid)
    assert res["terminal_state_enforced"] is True
    assert tid not in clean_engine._active_plans
    t_after = task_service.get_task(tid)
    assert t_after["state"] in [TaskState.FAILED.value, TaskState.STOPPED.value]
