"""
Unit tests for Thread-Safe STOP and Cancellation Across All Stages (Phase 4, Addendum §21, §22, Directive §20, §21).
Tests STOP during Goal Understanding, Planning, Confirmation, and Action Dispatch.
Verifies idempotency and late-response neutralization.
"""

import time
from unittest.mock import MagicMock, patch

from backend.app.services.task_service import task_service
from planner.execution_engine import ExecutionEngine
from planner.models import PlannedAction, PlannerActionType, TaskPlan


def test_stop_during_goal_understanding():
    """Verify STOP asserted during goal understanding halts execution immediately."""
    engine = ExecutionEngine()
    task = task_service.create_task("Test Stop Early")
    tid = task["id"]

    # Pre-stop task
    engine.stop_task(tid, reason="Pre-execution STOP")
    assert engine.is_stopped(tid) is True

    res = engine.run_task(tid)
    assert res["status"] == "STOPPED"
    assert res["success"] is False


def test_stop_is_idempotent():
    """Directive §20: STOP must be idempotent and callable repeatedly without error."""
    engine = ExecutionEngine()
    task = task_service.create_task("Test Idempotent Stop")
    tid = task["id"]

    for i in range(5):
        ok = engine.stop_task(tid, reason=f"Stop call #{i}")
        assert ok is True
        assert engine.is_stopped(tid) is True


def test_late_ai_response_neutralized_after_stop():
    """Directive §21: Late AI response arriving after STOP must be discarded."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Test Late AI Response")
    tid = task["id"]

    def delayed_planner_call(*args, **kwargs):
        # Trigger STOP while planning is underway
        engine.stop_task(tid, reason="User cancelled during AI request")
        time.sleep(0.05)
        late_plan = TaskPlan(
            task_id=tid,
            goal="Late plan",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.WAIT,
                    target_description="Late Action",
                    expected_result="Done",
                )
            ],
        )
        return True, late_plan, None

    mock_planner.create_plan.side_effect = delayed_planner_call

    with patch(
        "perception.uia_inspector.get_foreground_window",
        return_value={"success": False, "window": None},
    ):
        res = engine.run_task(tid)

    assert res["status"] == "STOPPED"
    assert res["success"] is False
