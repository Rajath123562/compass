"""
Idempotency and Non-Repeatable Action Verification Suite.
Tests:
  1. Non-repeatable action verification failure halts and transitions to BLOCKED without automatic retry.
  2. Non-repeatable action dispatch failure halts and transitions to FAILED without automatic retry.
  3. Repeatable action allows bounded retry up to max_retries.
"""

from unittest.mock import MagicMock, patch

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.execution_engine import ExecutionEngine
from planner.human_approval import human_approval_controller
from planner.stale_guard import StaleCheckResult
from planner.models import (
    Decision,
    GuidanceMode,
    PlannedAction,
    PlannerActionType,
    RiskLevel,
    TaskPlan,
    VerificationResult,
    VerificationStatus,
)


def test_non_repeatable_action_fails_verification_cannot_retry():
    """Verify that a non-repeatable action (e.g. destructive delete or payment) is NEVER automatically retried."""
    old_mode = human_approval_controller.mode
    human_approval_controller.set_mode(GuidanceMode.AUTONOMOUS)
    try:
        mock_planner = MagicMock()
        mock_verifier = MagicMock()
        engine = ExecutionEngine(
            planner=mock_planner, verifier=mock_verifier, max_retries_per_step=3
        )

        task = task_service.create_task("Non-Repeatable Verification Test")
        tid = task["id"]

        plan = TaskPlan(
            task_id=tid,
            goal="Delete user database",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.CLICK,
                    target_description="Delete Permanently",
                    expected_result="Database deleted",
                    safety_class="restricted",
                )
            ],
        )
        mock_planner.create_plan.return_value = (True, plan, None)

        # Verification fails
        mock_verifier.verify_action.return_value = VerificationResult(
            status=VerificationStatus.FAILED,
            details="Could not verify database deletion.",
        )

        with patch("planner.execution_engine.stale_guard.validate_freshness", return_value=StaleCheckResult(is_fresh=True, age_ms=10.0)):
            with patch(
                "planner.decision_engine.decision_engine.formulate_decision"
            ) as mock_dec:
                mock_dec.return_value = Decision(
                    decision_id="dec_non_repeatable",
                    task_id=tid,
                    action=PlannerActionType.CLICK,
                    target_description="Delete Permanently",
                    risk_level=RiskLevel.HIGH,
                    is_repeatable=False,  # Explicitly non-repeatable
                    human_explanation="Destructive action",
                )
                with patch.object(  # noqa: SIM117
                    engine,
                    "_dispatch_single_action",
                    return_value={"success": True, "action_type": "click"},
                ):
                    with patch(
                        "planner.human_approval.human_approval_controller.should_require_approval",
                        return_value=False,
                    ):
                        res = engine.run_task(tid)

        # Must NOT have retried 3 times; must halt on attempt 1 into BLOCKED
        assert res.get("status") == "BLOCKED"
        assert res.get("success") is False
        assert "Non-repeatable" in res.get("error", "")

        final_task = task_service.get_task(tid)
        assert final_task["state"] == TaskState.BLOCKED.value
    finally:
        human_approval_controller.set_mode(old_mode)


def test_non_repeatable_action_dispatch_failure_cannot_retry():
    """Verify that if dispatch fails for a non-repeatable action, automatic retry is prohibited."""
    old_mode = human_approval_controller.mode
    human_approval_controller.set_mode(GuidanceMode.AUTONOMOUS)
    try:
        mock_planner = MagicMock()
        mock_verifier = MagicMock()
        engine = ExecutionEngine(
            planner=mock_planner, verifier=mock_verifier, max_retries_per_step=3
        )

        task = task_service.create_task("Non-Repeatable Dispatch Failure Test")
        tid = task["id"]

        plan = TaskPlan(
            task_id=tid,
            goal="Submit payment",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.CLICK,
                    target_description="Submit Order",
                    expected_result="Order submitted",
                )
            ],
        )
        mock_planner.create_plan.return_value = (True, plan, None)

        with patch("planner.execution_engine.stale_guard.validate_freshness", return_value=StaleCheckResult(is_fresh=True, age_ms=10.0)):
            with patch(
                "planner.decision_engine.decision_engine.formulate_decision"
            ) as mock_dec:
                mock_dec.return_value = Decision(
                    decision_id="dec_submit",
                    task_id=tid,
                    action=PlannerActionType.CLICK,
                    target_description="Submit Order",
                    risk_level=RiskLevel.HIGH,
                    is_repeatable=False,
                    human_explanation="Submit order action",
                )
                with patch.object(  # noqa: SIM117
                    engine,
                    "_dispatch_single_action",
                    return_value={"success": False, "error": "Network blip during click"},
                ):
                    with patch(
                        "planner.human_approval.human_approval_controller.should_require_approval",
                        return_value=False,
                    ):
                        res = engine.run_task(tid)

        assert res.get("status") == "FAILED"
        assert res.get("success") is False
        assert "Non-repeatable" in res.get("error", "")

        final_task = task_service.get_task(tid)
        assert final_task["state"] == TaskState.FAILED.value
    finally:
        human_approval_controller.set_mode(old_mode)


def test_repeatable_action_allows_bounded_retry():
    """Verify that a safe repeatable action (e.g. read-only wait or observe) allows bounded retries."""
    old_mode = human_approval_controller.mode
    human_approval_controller.set_mode(GuidanceMode.AUTONOMOUS)
    try:
        mock_planner = MagicMock()
        mock_verifier = MagicMock()
        engine = ExecutionEngine(
            planner=mock_planner, verifier=mock_verifier, max_retries_per_step=2
        )

        task = task_service.create_task("Repeatable Retry Test")
        tid = task["id"]

        plan = TaskPlan(
            task_id=tid,
            goal="Observe state",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.OBSERVE,
                    target_description="Screen",
                    expected_result="Screen observed",
                )
            ],
        )
        mock_planner.create_plan.return_value = (True, plan, None)

        # Verification fails on first attempt, succeeds on second
        mock_verifier.verify_action.side_effect = [
            VerificationResult(
                status=VerificationStatus.FAILED, details="First attempt failed"
            ),
            VerificationResult(
                status=VerificationStatus.VERIFIED, details="Second attempt succeeded"
            ),
        ]
        mock_verifier.verify_final_goal_state.return_value = VerificationResult(
            status=VerificationStatus.VERIFIED,
            details="Final goal verified",
            evidence={"retry_verified": True},
        )

        with patch("planner.execution_engine.stale_guard.validate_freshness", return_value=StaleCheckResult(is_fresh=True, age_ms=10.0)):
            with patch(
                "planner.decision_engine.decision_engine.formulate_decision"
            ) as mock_dec:
                mock_dec.return_value = Decision(
                    decision_id="dec_observe",
                    task_id=tid,
                    action=PlannerActionType.OBSERVE,
                    target_description="Screen",
                    risk_level=RiskLevel.LOW,
                    is_repeatable=True,  # Repeatable
                    human_explanation="Observe screen",
                )
                with patch(
                    "planner.human_approval.human_approval_controller.should_require_approval",
                    return_value=False,
                ):
                    res = engine.run_task(tid)

        # Repeatable action retries and reaches COMPLETED
        assert res.get("success") is True
        assert res.get("status") == "COMPLETED"
        final_task = task_service.get_task(tid)
        assert final_task["state"] == TaskState.COMPLETED.value
    finally:
        human_approval_controller.set_mode(old_mode)
