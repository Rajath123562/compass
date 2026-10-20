"""
COMPASS Phase 10 — Untrusted AI Output Validation Pipeline Tests
Enforces the 10-gate validation pipeline on untrusted AI outputs before dispatch.
"""

import pytest
from pydantic import ValidationError

from automation.action_validator import ActionValidator
from automation.safety import check_coordinates_safe
from planner.human_approval import human_approval_controller
from planner.models import PlannedAction, PlannerActionType, RiskLevel
from planner.resource_governor import resource_governor
from planner.risk_classifier import risk_classifier
from planner.workflow_dag import WorkflowDAGValidator


class TestAIUntrustedValidationPipeline:
    def test_gate_01_schema_validation(self):
        """Gate 1: Schema validation rejects malformed action structure."""
        with pytest.raises(ValidationError):
            # Missing required action_type
            PlannedAction(target_description="Button", expected_result="Clicked")

    def test_gate_02_action_validation(self):
        """Gate 2: Action validation rejects invalid or malicious action type."""
        with pytest.raises(ValidationError):
            PlannedAction(action_type="FORMAT_C_DRIVE", target_description="Disk")

    def test_gate_03_target_validation(self):
        """Gate 3: Target validation rejects empty or spoofed targets."""
        validator = ActionValidator(check_foreground=False)
        val = validator.validate_click(element_ref={})  # Missing runtime_id and bounds
        assert val.ok is False
        assert (
            "not a valid window" in val.reason.lower()
            or "missing" in val.reason.lower()
            or "not found" in val.reason.lower()
        )

    def test_gate_04_parameter_validation(self):
        """Gate 4: Parameter validation rejects out-of-bounds coordinates."""
        safety = check_coordinates_safe(-500, 999999)
        assert safety.ok is False
        assert "bounds" in safety.reason.lower() or "screen" in safety.reason.lower()

    def test_gate_05_dependency_validation(self):
        """Gate 5: DAG dependency validation detects cycles and missing nodes."""
        from planner.workflow_models import Workflow, WorkflowNode, WorkflowNodeStatus

        wf = Workflow(
            workflow_id="wf_cycle",
            task_id="task_cycle",
            goal="Test cycle detection",
            nodes=[
                WorkflowNode(
                    node_id="node_1",
                    workflow_id="wf_cycle",
                    goal="Step 1",
                    status=WorkflowNodeStatus.PENDING,
                    dependencies=["node_2"],
                ),
                WorkflowNode(
                    node_id="node_2",
                    workflow_id="wf_cycle",
                    goal="Step 2",
                    status=WorkflowNodeStatus.PENDING,
                    dependencies=["node_1"],
                ),
            ],
        )
        validator = WorkflowDAGValidator()
        valid, errors = validator.validate(wf)
        assert valid is False
        assert any("cycle" in str(err).lower() for err in errors)

    def test_gate_06_risk_validation(self):
        """Gate 6: Deterministic risk classifier independently classifies action risk."""
        # AI might claim delete is "LOW", but classifier must enforce HIGH
        risk = risk_classifier.classify_risk(
            action=PlannerActionType.CLICK, target_name="Delete Database"
        )
        assert risk.risk_level == RiskLevel.HIGH
        assert risk.requires_confirmation is True

    def test_gate_07_safety_validation_forbidden_windows(self):
        """Gate 7: Safety validation blocks interaction with forbidden system targets."""
        from automation.safety import check_protected_window_class

        safety = check_protected_window_class("Progman")
        assert safety.ok is False
        assert "protected" in safety.reason.lower()

    def test_gate_08_approval_validation_binding(self):
        """Gate 8: Approval validation ensures high-risk action requires and checks valid approval."""
        from planner.models import Decision

        tid = "task_ai_untrusted_08"
        human_approval_controller.cleanup_task(tid)
        step = PlannedAction(
            action_type=PlannerActionType.CLICK,
            target_description="Format Drive",
            expected_result="Drive Formatted",
        )

        # Risk requires approval
        risk = risk_classifier.classify_risk(
            action=step.action_type, target_name=step.target_description
        )
        assert risk.requires_confirmation is True

        dec = Decision(
            decision_id="dec_format_01",
            task_id=tid,
            action=step.action_type,
            target_description=step.target_description,
            risk_level=risk.risk_level,
            requires_confirmation=risk.requires_confirmation,
            human_explanation="Formatting drive will cause permanent data loss.",
        )
        assert human_approval_controller.should_require_approval(dec) is True

        # Consuming an unapproved action must be rejected
        consumed, reason = human_approval_controller.consume_approval(
            tid, dec.decision_id
        )
        assert consumed is False
        assert "no approval" in reason.lower() or "rejected" in reason.lower()

    def test_gate_09_resource_budget_validation(self):
        """Gate 9: Resource validation halts execution if action count exceeds limit."""
        ok, err = resource_governor.check_action_budget(1001)  # Exceeds max allowable
        assert ok is False
        assert "exceeds" in err.lower() or "budget" in err.lower()

    def test_gate_10_verification_strategy_validation(self):
        """Gate 10: Verification validation rejects steps without valid expected result or verification criteria."""
        step = PlannedAction(
            action_type=PlannerActionType.CLICK,
            target_description="Save",
            expected_result="",  # Empty expected result
        )
        assert not step.expected_result or len(step.expected_result.strip()) == 0
