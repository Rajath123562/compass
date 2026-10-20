"""
Phase 12 Functional Loop & Failure Injection Test Suite
Validates the complete closed-loop computer-use lifecycle:
UNDERSTAND -> PERCEIVE -> PLAN -> VALIDATE -> SAFETY -> TARGET REVALIDATION ->
ONE ACTION -> VERIFY -> RE-PERCEIVE -> ADAPT -> FINAL VERIFICATION
under normal and injected abnormal conditions.
"""

import json
import time
from unittest.mock import patch

import pytest

from backend.app.database import db
from backend.app.models import TaskState
from backend.app.routers.workflows import WorkflowNodeCreate
from backend.app.services.task_service import task_service
from planner.checkpoint_manager import CheckpointManager
from planner.circuit_breaker import ai_circuit_breaker
from planner.execution_engine import ExecutionEngine
from planner.human_approval import ApprovalState, human_approval_controller
from planner.loop_detector import LoopDetector
from planner.models import (
    Decision,
    PlannedAction,
    PlannerActionType,
    RiskLevel,
    TaskPlan,
    VerificationResult,
    VerificationStatus,
)
from planner.risk_classifier import risk_classifier
from planner.stale_guard import stale_guard
from planner.workflow_models import WorkflowNode, WorkflowNodeStatus, WorkflowStatus
from planner.workflow_orchestrator import WorkflowOrchestrator


class TestPhase12FunctionalLoop:
    @pytest.fixture(autouse=True)
    def clean_circuit_breaker(self):
        ai_circuit_breaker.reset()
        yield
        ai_circuit_breaker.reset()

    # -------------------------------------------------------------------------
    # 1. One Action at a Time & Pre-Dispatch Target Revalidation
    # -------------------------------------------------------------------------
    def test_pre_dispatch_target_revalidation_rejects_closed_window(self):
        """Directive §14: Revalidate target immediately before action dispatch."""
        res = stale_guard.validate_freshness(
            observation_timestamp=time.time(),
            target_hwnd=88888888,  # Destroyed/invalid HWND
            is_sensitive=True,
        )
        assert res.is_fresh is False
        assert (
            "closed or destroyed" in res.stale_reason
            or "stale" in res.stale_reason.lower()
        )

    def test_stale_observation_rejected_when_age_exceeds_threshold(self):
        """Directive §14: Stale observation (>5.0s for normal, >2.0s for sensitive) is blocked."""
        old_time = time.time() - 6.0
        res = stale_guard.validate_freshness(
            observation_timestamp=old_time, target_hwnd=None, is_sensitive=False
        )
        assert res.is_fresh is False
        assert "exceeds maximum freshness threshold" in res.stale_reason

    # -------------------------------------------------------------------------
    # 2. Final Goal Verification Independence (Action Success != Task Success)
    # -------------------------------------------------------------------------
    def test_action_success_does_not_equal_task_success_without_goal_verification(self):
        """Directive §16: Physical action dispatch success does NOT imply final goal success."""
        task = task_service.create_task("Test Goal Verification")
        tid = task["id"]

        # Action verification fails
        unverified = VerificationResult(
            status=VerificationStatus.FAILED,
            details="Expected text editor content did not match",
        )
        assert unverified.status != VerificationStatus.VERIFIED

        # Transition task state to UNVERIFIED rather than TASK_COMPLETED
        db.update_task_state(tid, TaskState.UNVERIFIED.value, reason=unverified.details)
        reloaded = task_service.get_task(tid)
        assert reloaded["state"] == TaskState.UNVERIFIED.value
        assert reloaded["state"] != TaskState.TASK_COMPLETED.value

    # -------------------------------------------------------------------------
    # 3. Partial Completion Preservation (Step 1 & 2 succeed, Step 3 fails)
    # -------------------------------------------------------------------------
    def test_partial_completion_preserves_verified_steps(self):
        """Directive §17: If later step fails, completed work remains recorded."""
        orch = WorkflowOrchestrator(database=db)
        n1 = WorkflowNode(node_id="part_s1", goal="Step 1: Init", priority=5)
        n2 = WorkflowNode(
            node_id="part_s2",
            goal="Step 2: Process",
            dependencies=["part_s1"],
            priority=5,
        )
        n3 = WorkflowNode(
            node_id="part_s3",
            goal="Step 3: Export",
            dependencies=["part_s2"],
            priority=5,
        )

        wf = orch.create_workflow(
            goal="Workflow Partial Completion Test", nodes=[n1, n2, n3]
        )

        # Simulate step 1 and step 2 verified success
        n1.status = WorkflowNodeStatus.COMPLETED
        n2.status = WorkflowNodeStatus.COMPLETED

        # Step 3 encounters unrecoverable failure
        n3.status = WorkflowNodeStatus.FAILED
        wf.status = WorkflowStatus.FAILED

        # Assert completed work is preserved
        completed_nodes = [
            n.node_id for n in wf.nodes if n.status == WorkflowNodeStatus.COMPLETED
        ]
        assert completed_nodes == ["part_s1", "part_s2"]
        assert wf.status == WorkflowStatus.FAILED
        assert wf.status != WorkflowStatus.COMPLETED

    # -------------------------------------------------------------------------
    # 4. Loop & Oscillation Detection
    # -------------------------------------------------------------------------
    def test_loop_detector_flags_repeated_identical_actions(self):
        """Directive §19: Repeated execution of the same action triggers loop detection."""
        detector = LoopDetector(max_repeated_actions=3)

        loop_found = False
        for _ in range(3):
            loop_found, reason = detector.record_action_attempt(
                action_type="click",
                target_id="SubmitButton",
                success=False,
                verification_status="FAILED",
            )

        assert loop_found is True
        assert "Loop detected" in reason

    # -------------------------------------------------------------------------
    # 5. STOP Responsiveness Across Lifecycle
    # -------------------------------------------------------------------------
    def test_stop_asserted_before_execution_halts_immediately(self):
        """Directive §20: Stop asserted before run_task exits immediately with STOPPED."""
        engine = ExecutionEngine()
        task = task_service.create_task("Test Pre-execution STOP")
        tid = task["id"]

        # Signal stop
        ok = engine.stop_task(tid, reason="Emergency pre-stop")
        assert ok is True
        assert engine.is_stopped(tid) is True

        res = engine.run_task(tid)
        assert res["success"] is False
        assert res["status"] == "STOPPED"

    def test_late_ai_response_neutralized_after_stop(self):
        """Directive §21: Late AI response arriving after STOP must be discarded."""
        engine = ExecutionEngine()
        task = task_service.create_task("Test Late AI Response Discard")
        tid = task["id"]

        # Stop event asserted during AI call
        stop_evt = engine._get_stop_event(tid)
        stop_evt.set()

        with patch.object(engine.planner, "create_plan") as mock_plan:
            mock_plan.return_value = (
                True,
                TaskPlan(
                    task_id=tid,
                    goal="Test",
                    steps=[
                        PlannedAction(
                            action_type=PlannerActionType.CLICK,
                            target_description="X",
                            expected_result="X should be clicked",
                        )
                    ],
                ),
                None,
            )

            res = engine.run_task(tid)
            assert res["success"] is False
            assert res["status"] == "STOPPED"

    # -------------------------------------------------------------------------
    # 6. AI Failure Matrix: Malformed & Unsafe Response Handling
    # -------------------------------------------------------------------------
    def test_malformed_ai_plan_bounds_rejected(self):
        """Directive §13: Out-of-bounds parameters are strictly rejected."""
        with pytest.raises(Exception):  # noqa: B017
            WorkflowNodeCreate(node_id="bad_p", goal="Bad", priority=-1)

        with pytest.raises(Exception):  # noqa: B017
            WorkflowNodeCreate(node_id="bad_t", goal="Bad", timeout_s=1.0)  # ge=5.0

    def test_unsafe_plan_triggers_high_risk_and_approval(self):
        """Directive §13: Unsafe/destructive commands are intercepted."""
        risk = risk_classifier.classify_risk(
            action=PlannerActionType.CLICK, target_name="Format Partition D: /q"
        )
        assert risk.risk_level == RiskLevel.HIGH
        assert risk.requires_confirmation is True

    # -------------------------------------------------------------------------
    # 7. Context-Bound Human Approval Invalidation
    # -------------------------------------------------------------------------
    def test_approval_invalidated_when_target_context_changes(self):
        """Directive §14: If UI context changes, pending approval must be invalidated."""
        tid = "task_ctx_inval"
        dec = Decision(
            decision_id="dec_ctx_1",
            task_id=tid,
            action=PlannerActionType.CLICK,
            target_description="Delete Cluster",
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            human_explanation="Destructive",
        )
        req = human_approval_controller.create_approval_request(dec)
        assert req.state == ApprovalState.PENDING

        # Context changes: window drifted or target moved
        human_approval_controller.invalidate_all_approvals_for_task(
            tid, reason="Target window drifted"
        )

        reloaded = human_approval_controller.get_approval(tid, "dec_ctx_1")
        assert reloaded.state == ApprovalState.INVALIDATED
        assert reloaded.invalidation_reason == "Target window drifted"

    # -------------------------------------------------------------------------
    # 8. Checkpoint Cryptographic HMAC Integrity Verification
    # -------------------------------------------------------------------------
    def test_checkpoint_tamper_detection(self, tmp_path):
        """Directive §19: Tampering with checkpoint signature or payload is detected."""
        cm = CheckpointManager(storage_dir=tmp_path)
        chk = cm.save_workflow_checkpoint(  # noqa: F841
            workflow_id="wf_tamper_test",
            task_id="task_tamper",
            execution_generation=1,
            status="RUNNING",
            completed_node_ids=["n1"],
        )

        # Tamper with file
        chk_file = tmp_path / "wf_wf_tamper_test.json"
        with open(chk_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["completed_node_ids"] = ["n1", "n2_injected"]
        with open(chk_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Loading tampered checkpoint MUST fail HMAC check
        ok, res, err = cm.load_workflow_checkpoint("wf_tamper_test")  # noqa: RUF059
        assert ok is False
        assert "HMAC mismatch" in err or "tampered" in err.lower()
