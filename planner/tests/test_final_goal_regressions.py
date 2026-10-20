"""
COMPASS Mandatory Final-Goal & Action Verification Regression Suite
Covers:
- COMPASS-AUDIT-001: Missing, throwing, malformed or insufficient verifier never completes task.
- COMPASS-AUDIT-002: Generic completed-step count + healthy window rejected; goal-specific evidence required.
- COMPASS-AUDIT-003: OBSERVE is strictly observational and cannot launch processes or swallow launch failure.
- COMPASS-AUDIT-018: Heuristic focus and click shortcuts removed; concrete postconditions required.
- COMPASS-AUDIT-022: Overlay IPC failure returns failure/unverified, not false success.
"""

from unittest.mock import MagicMock, patch
import pytest

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
from planner.verification_engine import VerificationEngine
from automation.action_dispatcher import highlight_element


def test_missing_final_verifier_fails_closed():
    """COMPASS-AUDIT-001: Verifier object missing verify_final_goal_state method must block task, not complete it."""
    mock_planner = MagicMock()
    # Dummy verifier with verify_action but without verify_final_goal_state
    mock_verifier = MagicMock(spec=["verify_action"])
    mock_verifier.verify_action.return_value = VerificationResult(status=VerificationStatus.VERIFIED, details="step verified")
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Arbitrary Goal")
    tid = task["id"]
    plan = TaskPlan(
        task_id=tid,
        goal="Arbitrary Goal",
        steps=[
            PlannedAction(
                action_type=PlannerActionType.WAIT,
                target_description="wait step",
                expected_result="wait completed",
                parameters={"duration_ms": 10},
            )
        ],
    )
    mock_planner.create_plan.return_value = (True, plan, None)

    with patch.object(engine, "_dispatch_single_action", return_value={"success": True}), patch(
        "planner.human_approval.human_approval_controller.should_require_approval",
        return_value=False,
    ):
        res = engine.run_task(tid)

    assert res["success"] is False
    assert res["status"] in ("BLOCKED", "UNVERIFIED")
    assert task_service.get_task(tid)["state"] != TaskState.COMPLETED.value


def test_throwing_final_verifier_fails_closed():
    """COMPASS-AUDIT-001: Verifier raising an unexpected exception must block task, not synthesize completion."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    mock_verifier.verify_final_goal_state.side_effect = RuntimeError("Crash in external verifier")
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Arbitrary Goal")
    tid = task["id"]
    plan = TaskPlan(
        task_id=tid,
        goal="Arbitrary Goal",
        steps=[PlannedAction(action_type=PlannerActionType.WAIT, target_description="wait step", expected_result="wait completed", parameters={"duration_ms": 10})],
    )
    mock_planner.create_plan.return_value = (True, plan, None)
    mock_verifier.verify_action.return_value = VerificationResult(status=VerificationStatus.VERIFIED, details="step verified")

    with patch.object(engine, "_dispatch_single_action", return_value={"success": True}), patch(
        "planner.human_approval.human_approval_controller.should_require_approval",
        return_value=False,
    ):
        res = engine.run_task(tid)

    assert res["success"] is False
    assert res["status"] in ("BLOCKED", "UNVERIFIED")
    assert task_service.get_task(tid)["state"] != TaskState.COMPLETED.value


def test_malformed_verifier_output_fails_closed():
    """COMPASS-AUDIT-001: Verifier returning a non-VerificationResult type must block task."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    # Returns a string or dict instead of VerificationResult
    mock_verifier.verify_final_goal_state.return_value = {"status": "all_good"}
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Arbitrary Goal")
    tid = task["id"]
    plan = TaskPlan(
        task_id=tid,
        goal="Arbitrary Goal",
        steps=[PlannedAction(action_type=PlannerActionType.WAIT, target_description="wait step", expected_result="wait completed", parameters={"duration_ms": 10})],
    )
    mock_planner.create_plan.return_value = (True, plan, None)
    mock_verifier.verify_action.return_value = VerificationResult(status=VerificationStatus.VERIFIED, details="step verified")

    with patch.object(engine, "_dispatch_single_action", return_value={"success": True}), patch(
        "planner.human_approval.human_approval_controller.should_require_approval",
        return_value=False,
    ):
        res = engine.run_task(tid)

    assert res["success"] is False
    assert res["status"] in ("BLOCKED", "UNVERIFIED")
    assert task_service.get_task(tid)["state"] != TaskState.COMPLETED.value


def test_insufficient_evidence_fails_closed():
    """COMPASS-AUDIT-001: Verifier marking VERIFIED without required evidence payload is rejected."""
    mock_planner = MagicMock()
    mock_verifier = MagicMock()
    # Returns VERIFIED but evidence is empty/absent
    mock_verifier.verify_final_goal_state.return_value = VerificationResult(
        status=VerificationStatus.VERIFIED,
        details="Claimed success without evidence",
        evidence={},
    )
    engine = ExecutionEngine(planner=mock_planner, verifier=mock_verifier)

    task = task_service.create_task("Arbitrary Goal")
    tid = task["id"]
    plan = TaskPlan(
        task_id=tid,
        goal="Arbitrary Goal",
        steps=[PlannedAction(action_type=PlannerActionType.WAIT, target_description="wait step", expected_result="wait completed", parameters={"duration_ms": 10})],
    )
    mock_planner.create_plan.return_value = (True, plan, None)
    mock_verifier.verify_action.return_value = VerificationResult(status=VerificationStatus.VERIFIED, details="step verified")

    with patch.object(engine, "_dispatch_single_action", return_value={"success": True}), patch(
        "planner.human_approval.human_approval_controller.should_require_approval",
        return_value=False,
    ):
        res = engine.run_task(tid)

    assert res["success"] is False
    assert task_service.get_task(tid)["state"] != TaskState.COMPLETED.value


def test_generic_step_count_plus_healthy_window_rejected():
    """COMPASS-AUDIT-002: completed_step_count > 0 with active window must NOT verify unsupported/unproved goal."""
    verifier = VerificationEngine()
    snapshot = {
        "window": {"hwnd": 12345, "title": "Random Window - App"},
        "elements": [{"name": "Button1", "control_type": "Button"}],
    }

    # An arbitrary goal that cannot be verified from window title alone
    result = verifier.verify_final_goal_state(
        goal="Change audio sample rate to 96kHz",
        desired_final_state="Sample rate is 96kHz",
        current_snapshot=snapshot,
        completed_step_count=5,
        target_app="Random Window",
    )

    # Must be UNCERTAIN, NOT VERIFIED
    assert result.status != VerificationStatus.VERIFIED
    assert result.status == VerificationStatus.UNCERTAIN


def test_unrelated_healthy_window_rejected_for_typing():
    """COMPASS-AUDIT-002: Typing goal with unrelated window title and missing text fails verification."""
    verifier = VerificationEngine()
    snapshot = {
        "window": {"hwnd": 12345, "title": "Calculator"},
        "elements": [{"name": "One", "control_type": "Button"}],
    }

    result = verifier.verify_final_goal_state(
        goal="Type 'Hello World' into Notepad",
        desired_final_state="Text entered",
        current_snapshot=snapshot,
        completed_step_count=2,
        target_app="Notepad",
    )

    assert result.status == VerificationStatus.FAILED
    assert "target application" in result.details.lower() or "not active" in result.details.lower()


def test_observe_action_is_strictly_observational():
    """COMPASS-AUDIT-003: OBSERVE action with 'app' parameter does not spawn processes."""
    engine = ExecutionEngine()
    action = PlannedAction(
        action_type=PlannerActionType.OBSERVE,
        target_description="observe environment",
        expected_result="environment observed",
        parameters={"app": "malicious.exe --payload"},
    )
    with patch("os.startfile") as mock_startfile, patch("subprocess.Popen") as mock_popen:
        res = engine._dispatch_single_action(action, None, "task-1")

    assert res["success"] is True
    assert res["action_type"] == "observe"
    mock_startfile.assert_not_called()
    mock_popen.assert_not_called()


def test_heuristic_focus_shortcut_eliminated():
    """COMPASS-AUDIT-018: Action type being 'click' or 'focus' cannot bypass real foreground check."""
    verifier = VerificationEngine()
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="click button",
        expected_result="button clicked",
        parameters={},
    )
    # Target HWND is 100, but foreground window is 999
    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=999), patch(
        "ctypes.windll.user32.GetAncestor", return_value=0
    ):
        result = verifier.verify_action(
            action=action,
            post_snapshot={"elements": []},
            resolved_element={"hwnd": 100, "is_focused": False},
        )

    # Must NOT report VERIFIED simply because action_type was click
    assert result.status != VerificationStatus.VERIFIED


def test_overlay_ipc_failure_returns_false():
    """COMPASS-AUDIT-022: Overlay IPC unreachable must return success=False."""
    element = {"name": "TestBtn", "control_type": "Button", "bounds": {"left": 0, "top": 0, "right": 10, "bottom": 10}}
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        res = highlight_element(element, duration_ms=500)

    assert res.success is False
    assert res.error is not None
    assert "Overlay IPC unavailable" in res.error
