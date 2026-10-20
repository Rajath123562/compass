"""
Unit tests for ExecutionEngine, Task Loop, Retry Limits, and Thread-Safe STOP.
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


class TestExecutionEngine:
    def setup_method(self):
        self.mock_planner = MagicMock()
        self.mock_resolver = MagicMock()
        self.mock_verifier = MagicMock()
        self.mock_verifier.verify_final_goal_state.return_value = VerificationResult(
            status=VerificationStatus.VERIFIED,
            details="Final goal verified",
            evidence={"verified": True},
        )
        self.engine = ExecutionEngine(
            planner=self.mock_planner,
            resolver=self.mock_resolver,
            verifier=self.mock_verifier,
            max_retries_per_step=3,
        )

    def test_stop_mechanism_sets_flag_and_halts_task(self):
        task = task_service.create_task("Test STOP Task")
        task_id = task["id"]

        # Signal stop immediately
        assert self.engine.is_stopped(task_id) is False
        success = self.engine.stop_task(task_id, reason="User STOP test")
        assert success is True
        assert self.engine.is_stopped(task_id) is True

        # Running task after stop must return STOPPED immediately
        res = self.engine.run_task(task_id)
        assert res["status"] == "STOPPED"

    def test_single_action_loop_success(self):
        task = task_service.create_task("Simple Action Test")
        task_id = task["id"]

        # Mock planner returning 1 wait action
        plan = TaskPlan(
            task_id=task_id,
            goal="Wait test",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.WAIT,
                    target_description="Wait",
                    expected_result="Waited",
                    parameters={"duration_ms": 50},
                )
            ],
        )
        self.mock_planner.create_plan.return_value = (True, plan, None)
        self.mock_verifier.verify_action.return_value = VerificationResult(
            status=VerificationStatus.VERIFIED, details="Wait verified"
        )

        with patch(
            "perception.uia_inspector.get_foreground_window",
            return_value={"success": False, "window": None},
        ):
            res = self.engine.run_task(task_id)

        assert res["success"] is True
        assert res["status"] == "COMPLETED"
        updated = task_service.get_task(task_id)
        assert updated["state"] == TaskState.COMPLETED.value

    def test_concurrency_lock_prevents_duplicate_runs(self):
        task = task_service.create_task("Concurrency Lock Test")
        task_id = task["id"]

        # Acquire task lock manually
        lock = self.engine._get_task_lock(task_id)
        lock.acquire()
        try:
            res = self.engine.run_task(task_id)
            assert res["success"] is False
            assert "already executing" in res["error"]
        finally:
            lock.release()

    def test_bounded_retries_on_repeated_verification_failure(self):
        task = task_service.create_task("Retry Bounds Test")
        task_id = task["id"]

        plan = TaskPlan(
            task_id=task_id,
            goal="Fail test",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.WAIT,
                    target_description="Wait",
                    expected_result="Waited",
                    parameters={"duration_ms": 10},
                )
            ],
        )
        self.mock_planner.create_plan.return_value = (True, plan, None)
        # Verifier returns FAILED every time
        self.mock_verifier.verify_action.return_value = VerificationResult(
            status=VerificationStatus.FAILED, details="Mock failure"
        )

        with patch(
            "perception.uia_inspector.get_foreground_window",
            return_value={"success": False, "window": None},
        ):
            res = self.engine.run_task(task_id)

        # Must terminate with FAILED after 3 retries, not loop infinitely
        assert res["success"] is False
        assert res["status"] == "FAILED"
        updated = task_service.get_task(task_id)
        assert updated["state"] == TaskState.FAILED.value
