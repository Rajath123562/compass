"""
COMPASS Phase 10 — Reliability, Hardening, Reconciliation & Safety Tests
Verifies state reconciliation, incident logging, risk uncertainty protection,
atomic STOP barrier, loop/oscillation prevention, and secret masking.
"""

import time

from backend.app.database import db
from backend.app.services.task_service import task_service
from planner.execution_trace import ExecutionTraceManager
from planner.loop_detector import LoopDetector
from planner.models import PlannerActionType, RiskLevel, TaskState
from planner.reliability_monitor import (
    IncidentCategory,
    IncidentSeverity,
    reliability_monitor,
)
from planner.risk_classifier import risk_classifier


class TestPhase10ReliabilityAndHardening:
    def test_01_incident_logging_and_retrieval(self):
        """Reliability incident logging persists structured diagnostics."""
        tid = f"task_rel_test_{int(time.time())}"
        task_service.create_task("Test reliability incident logging")

        inc = reliability_monitor.record_incident(
            task_id=tid,
            category=IncidentCategory.UI_TARGET_LOST,
            severity=IncidentSeverity.HIGH,
            details={
                "target": "Save Button",
                "reason": "Element disappeared during animation",
            },
        )
        assert inc.incident_id.startswith("inc_")
        assert inc.category == IncidentCategory.UI_TARGET_LOST

        retrieved = reliability_monitor.get_incidents_for_task(tid)
        assert len(retrieved) >= 1
        assert retrieved[-1].incident_id == inc.incident_id

    def test_02_state_reconciliation_safely_resolves_stopped(self):
        """State reconciler reconciles in-memory STOP to STOPPED in DB without inventing success."""
        task = task_service.create_task("Test state reconciliation")
        tid = task["id"]

        # Simulate task in transitional PLANNING state in DB
        db.update_task_state(
            tid, TaskState.PLANNING.value, reason="Planning in progress"
        )

        # When in-memory execution stopped, reconciler must reconcile DB to STOPPED
        ok, msg = reliability_monitor.reconcile_task_state(tid, in_memory_stopped=True)
        assert ok is True

        reloaded = task_service.get_task(tid)
        assert reloaded["state"] == TaskState.STOPPED.value
        assert "Reconciled" in msg

    def test_03_risk_uncertainty_elevation(self):
        """Section 10: Uncertain or ambiguous targets are elevated to require confirmation, never downgraded to LOW."""
        risk_uncertain = risk_classifier.classify_risk(
            action=PlannerActionType.CLICK, target_name="uncertain_action_button"
        )
        assert risk_uncertain.requires_confirmation is True
        assert risk_uncertain.risk_level != RiskLevel.LOW

        risk_ambiguous = risk_classifier.classify_risk(
            action=PlannerActionType.CLICK, target_name="ambiguous_element"
        )
        assert risk_ambiguous.requires_confirmation is True
        assert risk_ambiguous.risk_level != RiskLevel.LOW

    def test_04_loop_detection_oscillation_protection(self):
        """Section 14: Loop detection halts repeated action attempts with bounded termination."""
        detector = LoopDetector(max_repeated_actions=3)
        # Attempt action 3 times
        detector.record_action_attempt("click", "target_btn", False, "FAILED")
        detector.record_action_attempt("click", "target_btn", False, "FAILED")
        loop_detected, reason = detector.record_action_attempt(
            "click", "target_btn", False, "FAILED"
        )
        assert loop_detected is True
        assert "Loop detected" in reason

    def test_05_secret_redaction_in_traces_and_logs(self):
        """Section 18 & 34: API keys and bearer tokens are automatically scrubbed from execution traces."""
        tm = ExecutionTraceManager()
        raw_goal = "Process user data using sk-proj-123456789012345678901234 and Bearer tok_sec998877"
        trace = tm.start_workflow_trace("wf_test_sec", "task_sec", raw_goal)

        assert "sk-proj-" not in trace.goal
        assert "tok_sec998877" not in trace.goal
        assert "[REDACTED_API_KEY]" in trace.goal
        assert "[REDACTED_SECRET]" in trace.goal
