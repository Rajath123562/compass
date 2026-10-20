"""
Unit tests for Human Approval Boundaries & Consequential Action Guards (Phase 6, Capability H, I, §10-§14).
Verifies that consequential actions strictly require human approval, approval is stateful and context-bound,
and approval is invalidated if context shifts.
"""

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.execution_controller import MultiStepExecutionController
from planner.human_approval import ApprovalState, HumanApprovalController
from planner.models import PlannerActionType, RiskLevel


def test_consequential_action_blocks_without_approval():
    """ExecutionController halts with SAFETY_BLOCKED when encountering an unapproved consequential action."""
    controller = MultiStepExecutionController()
    task = task_service.create_task("Test Consequential Action Block")
    tid = task["id"]

    # Run a consequential goal: delete files
    res = controller.run_multistep_task(tid, "Delete system cache and purge files")
    assert res["status"] in ["SAFETY_BLOCKED", "BLOCKED"]
    assert res["success"] is False
    assert "consequential" in res["error"].lower()

    t_rec = task_service.get_task(tid)
    assert t_rec["state"] in [TaskState.SAFETY_BLOCKED.value, TaskState.BLOCKED.value]


from planner.models import ConfidenceLevel, Decision


def make_test_decision(
    task_id: str,
    decision_id: str,
    risk: RiskLevel = RiskLevel.CONSEQUENTIAL,
    obs_id: str = "obs_1",
) -> Decision:
    return Decision(
        decision_id=decision_id,
        task_id=task_id,
        observation_id=obs_id,
        action=PlannerActionType.CLICK,
        target_description="Delete Button",
        confidence=ConfidenceLevel.HIGH,
        confidence_score=0.95,
        risk_level=risk,
        requires_confirmation=True,
        human_explanation="Consequential file deletion",
        timestamp=1000.0,
    )


def test_human_approval_lifecycle():
    """Human approval lifecycle: REQUEST -> GRANT -> CONSUME."""
    hac = HumanApprovalController()
    tid = "task_appr_1"
    dec = make_test_decision(tid, "dec_delete")

    # Request approval for a consequential step
    req = hac.create_approval_request(dec)
    assert req.state == ApprovalState.PENDING

    # User grants approval
    ok = hac.grant_approval(tid, "dec_delete")
    assert ok is True

    # Validate approval matches
    valid, err = hac.validate_approval_binding(  # noqa: RUF059
        task_id=tid,
        decision_id="dec_delete",
        current_action=dec.action,
        current_target_identifier=dec.target_description,
        current_hwnd=None,
        current_app="",
        current_bounds=None,
        current_time=req.observation_timestamp + 1.0,
    )
    assert valid is True

    # Consuming the approval marks it CONSUMED (cannot be reused)
    ok_cons, _ = hac.consume_approval(tid, "dec_delete")
    assert ok_cons is True
    valid_reused, err2 = hac.validate_approval_binding(
        task_id=tid,
        decision_id="dec_delete",
        current_action=dec.action,
        current_target_identifier=dec.target_description,
        current_hwnd=None,
        current_app="",
        current_bounds=None,
        current_time=req.observation_timestamp + 2.0,
    )
    assert valid_reused is False
    assert "consumed" in err2.lower() or "not granted" in err2.lower()


def test_approval_invalidated_on_stale_observation():
    """Approval granted on observation_1 is invalidated if observation shifts."""
    hac = HumanApprovalController()
    tid = "task_appr_stale"
    dec = make_test_decision(tid, "dec_1", obs_id="obs_alpha")

    req = hac.create_approval_request(dec)
    hac.grant_approval(tid, "dec_1")

    # Observation shifted past 10-second threshold
    valid, err = hac.validate_approval_binding(
        task_id=tid,
        decision_id="dec_1",
        current_action=dec.action,
        current_target_identifier=dec.target_description,
        current_hwnd=None,
        current_app="",
        current_bounds=None,
        current_time=req.observation_timestamp + 30.0,  # 30 seconds later
    )
    assert valid is False
    assert (
        "stale" in err.lower()
        or "elapsed" in err.lower()
        or "invalidated" in err.lower()
    )
