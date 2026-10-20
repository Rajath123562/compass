"""
Deep Concurrency and Thread-Safety Verification Suite.
Tests:
  1. Duplicate execution prevention
  2. Simultaneous task execution
  3. STOP vs execution race
  4. Approval vs STOP race
  5. Concurrent replanning
  6. Late AI response after cancellation
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.execution_engine import ExecutionEngine
from planner.goal_understanding import GoalUnderstandingResult
from planner.models import (
    PlannedAction,
    PlannerActionType,
    RiskLevel,
    TaskPlan,
    VerificationResult,
    VerificationStatus,
)
from planner.recovery_engine import recovery_engine
from planner.stale_guard import StaleCheckResult


@pytest.fixture(autouse=True)
def fast_concurrency_env():
    fast_goal = GoalUnderstandingResult(
        raw_goal="Concurrency Test",
        objective="Concurrency Test",
        target_application=None,
        safety_level=RiskLevel.LOW,
        is_ambiguous=False,
        desired_final_state="",
    )
    with patch(
        "planner.execution_engine.goal_understanding_engine.understand_goal",
        return_value=fast_goal,
    ), patch(
        "planner.execution_engine.uia_inspector.get_foreground_window",
        return_value={"success": True, "window": {"hwnd": 0, "title": "Test"}},
    ), patch(
        "planner.execution_engine.uia_inspector.get_element_tree",
        return_value={"elements": []},
    ), patch(
        "planner.execution_engine.stale_guard.validate_freshness",
        return_value=StaleCheckResult(is_fresh=True, age_ms=10.0),
    ):
        yield


def test_duplicate_execution_prevention():
    """Verify second concurrent run_task call on the same task ID is immediately rejected."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Duplicate Execution Concurrency Test")
    tid = task["id"]

    plan = TaskPlan(
        task_id=tid,
        goal="Duplicate test",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.WAIT,
                target_description="Wait",
                expected_result="Done",
                parameters={"duration_ms": 300},
            )
        ],
    )
    mock_planner.create_plan.return_value = (True, plan, None)
    mock_verifier.verify_action.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED, details="OK"
    )
    mock_verifier.verify_final_goal_state.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED,
        details="Final goal verified",
        evidence={"verified": True},
    )

    results = []

    def worker():
        res = engine.run_task(tid)
        results.append(res)

    t1 = threading.Thread(target=worker)
    t1.start()
    time.sleep(0.05)  # Let t1 acquire lock

    # Second concurrent call
    t2 = threading.Thread(target=worker)
    t2.start()

    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert len(results) == 2
    # One must have failed with lock error
    lock_failures = [
        r
        for r in results
        if not r.get("success") and "already executing" in str(r.get("error"))
    ]
    assert len(lock_failures) == 1


def test_simultaneous_task_execution():
    """Verify two distinct tasks execute concurrently without interference."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task_a = task_service.create_task("Simultaneous Task A")
    task_b = task_service.create_task("Simultaneous Task B")
    tid_a = task_a["id"]
    tid_b = task_b["id"]

    plan_a = TaskPlan(
        task_id=tid_a,
        goal="A",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.WAIT,
                target_description="A",
                expected_result="Done",
                parameters={"duration_ms": 100},
            )
        ],
    )
    plan_b = TaskPlan(
        task_id=tid_b,
        goal="B",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.WAIT,
                target_description="B",
                expected_result="Done",
                parameters={"duration_ms": 100},
            )
        ],
    )

    def create_plan_mock(goal, ui_snapshot, task_id, **kwargs):
        if task_id == tid_a:
            return True, plan_a, None
        return True, plan_b, None

    mock_planner.create_plan.side_effect = create_plan_mock
    mock_verifier.verify_action.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED, details="OK"
    )
    mock_verifier.verify_final_goal_state.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED,
        details="Final goal verified",
        evidence={"verified": True},
    )

    results = {}

    def worker_a():
        results["a"] = engine.run_task(tid_a)

    def worker_b():
        results["b"] = engine.run_task(tid_b)

    t1 = threading.Thread(target=worker_a)
    t2 = threading.Thread(target=worker_b)
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert results["a"].get("success") is True
    assert results["b"].get("success") is True
    assert results["a"].get("status") == "COMPLETED"
    assert results["b"].get("status") == "COMPLETED"


def test_stop_vs_execution_race():
    """Verify STOP asserted concurrently while task is running terminates it safely."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("STOP Race Test")
    tid = task["id"]

    # Plan with slow wait actions
    steps = [
        PlannedAction(
            action_type=PlannerActionType.WAIT,
            target_description=f"Wait #{i}",
            expected_result="Done",
            parameters={"duration_ms": 300},
        )
        for i in range(6)
    ]
    plan = TaskPlan(task_id=tid, goal="Race", steps=steps)
    mock_planner.create_plan.return_value = (True, plan, None)
    mock_verifier.verify_action.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED, details="OK"
    )

    result = {}

    def worker():
        result["res"] = engine.run_task(tid)

    t = threading.Thread(target=worker)
    t.start()
    for _ in range(40):
        if tid in engine._active_plans:
            break
        time.sleep(0.02)
    time.sleep(0.08)  # Ensure first step begins

    # Assert STOP concurrently
    engine.stop_task(tid, reason="Concurrent STOP asserted")
    t.join(timeout=5.0)

    assert result["res"].get("status") == "STOPPED"
    final_task = task_service.get_task(tid)
    assert final_task["state"] in [TaskState.STOPPED.value, TaskState.CANCELLED.value]


def test_approval_vs_stop_race():
    """Verify STOP asserted while waiting in WAITING_CONFIRMATION halts immediately without timeout."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    from planner.human_approval import human_approval_controller
    from planner.models import GuidanceMode

    old_mode = human_approval_controller.mode
    human_approval_controller.set_mode(
        GuidanceMode.GUIDE
    )  # Requires confirmation for all

    try:
        task = task_service.create_task("Approval STOP Race Test")
        tid = task["id"]

        plan = TaskPlan(
            task_id=tid,
            goal="Approval race",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.CLICK,
                    target_description="Target Button",
                    expected_result="Clicked",
                )
            ],
        )
        mock_planner.create_plan.return_value = (True, plan, None)

        result = {}
        t0 = time.time()

        def worker():
            result["res"] = engine.run_task(tid, confirmation_timeout_s=10.0)

        t = threading.Thread(target=worker)
        t.start()
        time.sleep(0.15)  # Let it enter WAITING_CONFIRMATION

        # Assert STOP while it is waiting for confirmation
        engine.stop_task(tid, reason="User STOP during approval wait")
        t.join(timeout=3.0)
        elapsed = time.time() - t0

        assert elapsed < 5.0, (
            "Engine did not break out of confirmation wait promptly upon STOP"
        )
        assert result["res"].get("status") == "STOPPED"
    finally:
        human_approval_controller.set_mode(old_mode)


def test_concurrent_replanning():
    """Verify concurrent calls to recovery engine replanning are safe."""
    completed = [
        PlannedAction(
            step_number=1,
            action_type=PlannerActionType.CLICK,
            target_description="Menu",
            expected_result="Open",
        )
    ]
    new_step = PlannedAction(
        step_number=2,
        action_type=PlannerActionType.CLICK,
        target_description="Save",
        expected_result="Saved",
    )

    plans = []

    def replan_worker(idx):
        p = recovery_engine.synthesize_adaptive_plan(
            task_id=f"concurrent_task_{idx}",
            original_goal="Goal",
            completed_steps=completed,
            remaining_steps=[],
            replan_steps=[new_step],
            plan_version=idx,
        )
        plans.append(p)

    threads = [threading.Thread(target=replan_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(plans) == 10
    for p in plans:
        assert len(p.steps) == 2
        assert p.steps[0].target_description == "Menu"
        assert p.steps[1].target_description == "Save"


def test_late_ai_response_after_cancellation():
    """Verify late AI response returning after task cancellation is quarantined and discarded."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Late AI Test")
    tid = task["id"]

    def slow_plan(*args, **kwargs):
        # Simulate AI taking time while user cancels
        engine.stop_task(tid, reason="Cancelled during AI generation")
        time.sleep(0.05)
        late_plan = TaskPlan(
            task_id=tid,
            goal="Late plan",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.WAIT,
                    target_description="Late",
                    expected_result="Done",
                )
            ],
        )
        return True, late_plan, None

    mock_planner.create_plan.side_effect = slow_plan

    res = engine.run_task(tid)
    assert res["status"] == "STOPPED"
    assert res["success"] is False
    final_task = task_service.get_task(tid)
    assert final_task["state"] in [TaskState.STOPPED.value, TaskState.CANCELLED.value]
