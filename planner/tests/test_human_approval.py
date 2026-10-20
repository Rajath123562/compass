"""
Unit tests for Human Approval Controller and Anti-Bypass Validation (Phase 4, Addendum §6, §7, Directive §9, §10).
"""

import time

from planner.human_approval import HumanApprovalController
from planner.models import (
    ConfidenceLevel,
    Decision,
    GuidanceMode,
    PlannerActionType,
    RiskLevel,
)


def make_test_decision(
    risk: RiskLevel = RiskLevel.LOW,
    action: PlannerActionType = PlannerActionType.CLICK,
    target_desc: str = "TestBtn",
) -> Decision:
    return Decision(
        decision_id="dec_test_001",
        task_id="task_test_001",
        observation_id="obs_001",
        action=action,
        target_description=target_desc,
        confidence=ConfidenceLevel.HIGH,
        confidence_score=0.9,
        risk_level=risk,
        requires_confirmation=(risk == RiskLevel.HIGH),
        human_explanation="Test action",
    )


def test_high_risk_requires_approval_in_all_modes():
    """
    Directive §9 & Addendum §6: Across GUIDE, ASSIST, CONFIRM, AUTONOMOUS:
    HIGH-risk actions MUST require explicit human approval.
    """
    controller = HumanApprovalController()
    high_dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Delete All")

    for mode in [
        GuidanceMode.GUIDE,
        GuidanceMode.ASSIST,
        GuidanceMode.CONFIRM,
        GuidanceMode.AUTONOMOUS,
    ]:
        controller.set_mode(mode)
        assert controller.should_require_approval(high_dec) is True, (
            f"Failed in mode {mode.value}"
        )


def test_autonomous_mode_allows_low_and_medium():
    controller = HumanApprovalController(default_mode=GuidanceMode.AUTONOMOUS)
    low_dec = make_test_decision(risk=RiskLevel.LOW, target_desc="View Menu")
    med_dec = make_test_decision(
        risk=RiskLevel.MEDIUM, action=PlannerActionType.TYPE, target_desc="Edit Area"
    )
    high_dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Format Disk")

    assert controller.should_require_approval(low_dec) is False
    assert controller.should_require_approval(med_dec) is False
    assert controller.should_require_approval(high_dec) is True


def test_approval_anti_bypass_target_change():
    """Directive §10 & Addendum §7: Invalidate approval if target changes."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Current execution has drifted: target is now "Button B"
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button B",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid is False
    assert "Target changed" in reason


def test_approval_anti_bypass_action_change():
    """Directive §10 & Addendum §7: Invalidate approval if action changes."""
    controller = HumanApprovalController()
    dec = make_test_decision(
        risk=RiskLevel.HIGH, action=PlannerActionType.CLICK, target_desc="Button A"
    )
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Action changed from click to type
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.TYPE,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid is False
    assert "Action changed" in reason


def test_approval_anti_bypass_hwnd_change():
    """Directive §10 & Addendum §7: Invalidate approval if target window changes."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # HWND changed from 100 to 999
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=999,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid is False
    assert "HWND changed" in reason


def test_approval_anti_bypass_material_movement():
    """Directive §10 & Addendum §7: Invalidate approval if element shifted materially."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    orig_bounds = {"left": 10, "top": 10}
    controller.create_approval_request(dec, window_hwnd=100, target_bounds=orig_bounds)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Shifted to (200, 200) -> distance > 120px
    shifted_bounds = {"left": 200, "top": 200}
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds=shifted_bounds,
    )
    assert valid is False
    assert "moved materially" in reason


def test_approval_anti_bypass_parameters_change():
    """Directive §5: Invalidate approval if action parameters change."""
    controller = HumanApprovalController()
    dec = make_test_decision(
        risk=RiskLevel.HIGH, action=PlannerActionType.TYPE, target_desc="Input"
    )
    dec.parameters = {"text": "harmless query"}
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Parameters changed to destructive command
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.TYPE,
        current_target_identifier="Input",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
        current_parameters={"text": "drop database users"},
    )
    assert valid is False
    assert "Action parameters changed" in reason


def test_approval_anti_bypass_application_change():
    """Directive §5: Invalidate approval if target application changes."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(
        dec, window_hwnd=100, application_name="SafeEditor"
    )
    controller.grant_approval("task_test_001", "dec_test_001")

    # Application changed to CommandPrompt
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="CommandPrompt",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid is False
    assert "Application changed" in reason


def test_approval_anti_bypass_target_disappears():
    """Directive §5: Invalidate approval if target element disappeared."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(
        dec, window_hwnd=100, target_bounds={"left": 10, "top": 10}
    )
    controller.grant_approval("task_test_001", "dec_test_001")

    # Target element disappeared (current_bounds is None)
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds=None,
    )
    assert valid is False
    assert "disappeared" in reason


def test_approval_anti_bypass_stale_observation():
    """Directive §5 & §9: Invalidate approval if observation became stale."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    dec.timestamp = time.time() - 30.0  # 30 seconds ago
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Validating with max observation age of 5.0 seconds -> must fail
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
        max_observation_age_s=5.0,
    )
    assert valid is False
    assert "stale" in reason


def test_approval_anti_bypass_display_context_change():
    """Directive §5 & §10: Invalidate approval if screen/display context changed."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(
        dec, window_hwnd=100, display_context={"resolution": "1920x1080", "dpi": 96}
    )
    controller.grant_approval("task_test_001", "dec_test_001")

    # Screen resolution changed to 2560x1440
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
        current_display_context={"resolution": "2560x1440", "dpi": 144},
    )
    assert valid is False
    assert "display context" in reason.lower()


def test_approval_anti_bypass_task_or_decision_mismatch():
    """Directive §5: Invalidate if task_id or decision_id do not match."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Mismatched decision_id
    valid1, _ = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_DIFFERENT",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid1 is False

    # Mismatched task_id
    valid2, _ = controller.validate_approval_binding(
        task_id="task_DIFFERENT",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid2 is False


def test_approval_consumed_once_only():
    """Directive §4, §9: Approvals are single-use tokens; second consume attempt fails."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # First consumption succeeds
    ok1, msg1 = controller.consume_approval("task_test_001", "dec_test_001")
    assert ok1 is True
    assert "successfully consumed" in msg1.lower()

    # Second consumption fails
    ok2, msg2 = controller.consume_approval("task_test_001", "dec_test_001")
    assert ok2 is False
    assert "already" in msg2.lower() and "consumed" in msg2.lower()


def test_replay_approval_rejected():
    """Directive §4, §9: Replaying a consumed approval token is strictly rejected."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100)
    controller.grant_approval("task_test_001", "dec_test_001")

    # Consume the approval
    ok, _ = controller.consume_approval("task_test_001", "dec_test_001")
    assert ok is True

    # Attempting to validate the binding with consumed approval must fail
    valid, reason = controller.validate_approval_binding(
        task_id="task_test_001",
        decision_id="dec_test_001",
        current_action=PlannerActionType.CLICK,
        current_target_identifier="Button A",
        current_hwnd=100,
        current_app="TestApp",
        current_bounds={"left": 10, "top": 10},
    )
    assert valid is False
    assert "consumed" in reason.lower() or "replay" in reason.lower()


def test_cannot_consume_unapproved():
    """Cannot consume an approval that is still PENDING or REJECTED."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100)

    # Still pending
    ok, msg = controller.consume_approval("task_test_001", "dec_test_001")
    assert ok is False
    assert "PENDING" in msg

    # Reject
    controller.reject_approval("task_test_001", "dec_test_001")
    ok, msg = controller.consume_approval("task_test_001", "dec_test_001")
    assert ok is False
    assert "REJECTED" in msg


def test_expired_approval_cannot_be_consumed():
    """Expired approval transitions to INVALIDATED and cannot be consumed."""
    controller = HumanApprovalController()
    dec = make_test_decision(risk=RiskLevel.HIGH, target_desc="Button A")
    controller.create_approval_request(dec, window_hwnd=100, timeout_seconds=0.01)
    time.sleep(0.02)

    ok, msg = controller.consume_approval("task_test_001", "dec_test_001")
    assert ok is False
    assert "expired" in msg.lower() or "INVALIDATED" in msg
