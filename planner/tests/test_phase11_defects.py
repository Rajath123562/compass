"""
Phase 11 Defect Elimination & Architecture Verification Tests
Verifies targeted fixes for DEF-P11-01 through DEF-P11-05 under zero-regression contract.
"""

import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.app.database import db
from backend.app.models import TaskState
from backend.app.routers.workflows import WorkflowNodeCreate
from backend.app.services.task_service import task_service
from planner.circuit_breaker import ai_circuit_breaker
from planner.execution_engine import ExecutionEngine
from planner.workflow_orchestrator import WorkflowOrchestrator


class TestPhase11Defects:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Ensure clean circuit breaker state before and after each test."""
        orig_timeout = ai_circuit_breaker._recovery_timeout_s
        ai_circuit_breaker.reset()
        yield
        ai_circuit_breaker.reset()
        ai_circuit_breaker._recovery_timeout_s = orig_timeout

    # -------------------------------------------------------------------------
    # DEF-P11-01: AI Circuit Breaker / Unavailability Truthful State
    # -------------------------------------------------------------------------
    def test_def_p11_01_circuit_breaker_open_transitions_to_ai_unavailable(self):
        """DEF-P11-01: Execution engine must transition task to AI_UNAVAILABLE when breaker is open."""
        engine = ExecutionEngine()
        task = task_service.create_task("Test DEF-P11-01: Circuit Breaker Open")
        tid = task["id"]

        # Trip circuit breaker and ensure recovery timeout doesn't expire during slow network calls
        ai_circuit_breaker._recovery_timeout_s = 60.0
        for _ in range(6):
            ai_circuit_breaker.record_failure()
        assert ai_circuit_breaker.can_execute() is False

        captured_events = []

        def event_sink(ev, payload):
            captured_events.append((ev, payload))

        res = engine.run_task(tid, on_event=event_sink)

        # Result dictionary indicates failure, with error_code AI_UNAVAILABLE
        assert res["success"] is False
        assert res["status"] == "FAILED"
        assert res.get("error_code") == "AI_UNAVAILABLE"
        assert "circuit breaker is OPEN" in res["error"]

        # Database state recorded as FAILED with AI_UNAVAILABLE event
        reloaded = task_service.get_task(tid)
        assert reloaded["state"] == TaskState.FAILED.value

        # Event stream must have emitted task_ai_unavailable
        event_types = [ev[0] for ev in captured_events]
        assert "task_ai_unavailable" in event_types

    def test_def_p11_01_planning_ai_failure_transitions_safely(self):
        """DEF-P11-01: If planner fails due to AI gateway offline, task transitions safely."""
        engine = ExecutionEngine()
        task = task_service.create_task("Test DEF-P11-01: Planning Offline")
        tid = task["id"]

        with patch.object(
            engine.planner,
            "create_plan",
            return_value=(False, None, "AI gateway offline"),
        ):
            res = engine.run_task(tid)
            assert res["success"] is False
            assert res["status"] == "FAILED"
            assert "AI gateway offline" in res["error"]

            reloaded = task_service.get_task(tid)
            assert reloaded["state"] == TaskState.FAILED.value

    # -------------------------------------------------------------------------
    # DEF-P11-02: Terminal State Preservation in Resource Cleanup
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "terminal_state",
        [
            TaskState.TASK_COMPLETED,
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.STOPPED,
            TaskState.CANCELLED,
            TaskState.BLOCKED,
            TaskState.UNVERIFIED,
            TaskState.AI_UNAVAILABLE,
            TaskState.SAFETY_BLOCKED,
        ],
    )
    def test_def_p11_02_cleanup_preserves_all_terminal_states(self, terminal_state):
        """DEF-P11-02: cleanup_task_resources must never overwrite any valid terminal state."""
        engine = ExecutionEngine()
        task = task_service.create_task(
            f"Test DEF-P11-02: Terminal {terminal_state.value}"
        )
        tid = task["id"]

        # Force state to terminal state in database
        db.update_task_state(
            tid, terminal_state.value, reason="Test pre-set terminal state"
        )
        assert task_service.get_task(tid)["state"] == terminal_state.value

        # Run cleanup
        cleanup_report = engine.cleanup_task_resources(tid)
        assert cleanup_report["terminal_state_enforced"] is False

        # State must NOT be mutated to FAILED or STOPPED
        after_cleanup = task_service.get_task(tid)
        assert after_cleanup["state"] == terminal_state.value

    def test_def_p11_02_cleanup_forces_transitional_to_failed(self):
        """DEF-P11-02: Transitional non-terminal states are safely closed to FAILED on abnormal exit."""
        engine = ExecutionEngine()
        task = task_service.create_task("Test DEF-P11-02: Transitional cleanup")
        tid = task["id"]

        db.update_task_state(tid, TaskState.PLANNING.value, reason="Test in-flight")
        assert task_service.get_task(tid)["state"] == TaskState.PLANNING.value

        cleanup_report = engine.cleanup_task_resources(tid)
        assert cleanup_report["terminal_state_enforced"] is True

        after_cleanup = task_service.get_task(tid)
        assert after_cleanup["state"] == TaskState.FAILED.value

    # -------------------------------------------------------------------------
    # DEF-P11-03: Workflow DB Reconstruction Priority Clamping & Case Normalization
    # -------------------------------------------------------------------------
    def test_def_p11_03_load_workflow_from_db_handles_zero_priority(self):
        """DEF-P11-03: _load_workflow_from_db clamps priority <=0 to 1 and lower risk to upper."""
        orchestrator = WorkflowOrchestrator(database=db)
        wfid = "wf_def_p11_03_test"
        task = task_service.create_task("Task for P11-03")
        tid = task["id"]

        # Manually insert a workflow and node with priority=0 and lowercase risk
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO workflows (workflow_id, task_id, goal, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (wfid, tid, "Goal P11-03", "READY", 1000.0, 1000.0),
        )

        node_meta = json.dumps(
            {"priority": 0, "risk_level": "medium", "approval_required": False}
        )
        cursor.execute(
            """
            INSERT OR REPLACE INTO workflow_nodes (node_id, workflow_id, goal, status, dependencies, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("node_1", wfid, "Node 1", "PENDING", "[]", node_meta, 1000.0, 1000.0),
        )
        conn.commit()

        # Reconstructing workflow from database must NOT crash with ValidationError
        loaded_wf = orchestrator._load_workflow_from_db(wfid)
        assert loaded_wf is not None
        assert len(loaded_wf.nodes) == 1
        node = loaded_wf.nodes[0]
        assert node.priority == 1  # Clamped from 0 to 1
        assert node.risk_level == "MEDIUM"  # Uppercased from medium

    def test_def_p11_03_workflow_node_create_pydantic_validation(self):
        """DEF-P11-03: WorkflowNodeCreate validates priority bounds (1..10)."""
        # Valid priority
        valid_node = WorkflowNodeCreate(node_id="n1", goal="Goal", priority=5)
        assert valid_node.priority == 5

        # Invalid priority < 1
        with pytest.raises(Exception):  # noqa: B017
            WorkflowNodeCreate(node_id="n2", goal="Goal", priority=0)

        # Invalid priority > 10
        with pytest.raises(Exception):  # noqa: B017
            WorkflowNodeCreate(node_id="n3", goal="Goal", priority=11)

    # -------------------------------------------------------------------------
    # DEF-P11-04: TaskService.stop_task Terminal State Immutability
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "terminal_state",
        [
            TaskState.COMPLETED,
            TaskState.TASK_COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.BLOCKED,
            TaskState.UNVERIFIED,
            TaskState.AI_UNAVAILABLE,
            TaskState.SAFETY_BLOCKED,
        ],
    )
    def test_def_p11_04_stop_task_rejects_all_terminal_states(self, terminal_state):
        """DEF-P11-04: stop_task must raise HTTPException 400 when task is already in any terminal state."""
        task = task_service.create_task(
            f"Test DEF-P11-04 Terminal {terminal_state.value}"
        )
        tid = task["id"]

        db.update_task_state(tid, terminal_state.value, reason="Pre-set terminal")

        with pytest.raises(HTTPException) as exc_info:
            task_service.stop_task(tid, reason="Attempted stop")

        assert exc_info.value.status_code == 400
        assert (
            "already reached terminal state" in exc_info.value.detail
            or "already completed" in exc_info.value.detail
        )

        # State must remain untouched
        assert task_service.get_task(tid)["state"] == terminal_state.value

    def test_def_p11_04_stop_task_is_idempotent_on_stopped_state(self):
        """DEF-P11-04: Repeated stop on a STOPPED task is idempotent and does not raise 400."""
        task = task_service.create_task("Test DEF-P11-04 Idempotent Stop")
        tid = task["id"]

        first_stop = task_service.stop_task(tid, reason="Initial stop")
        assert first_stop["state"] == TaskState.STOPPED.value

        second_stop = task_service.stop_task(tid, reason="Repeat stop")
        assert second_stop["state"] == TaskState.STOPPED.value

    # -------------------------------------------------------------------------
    # DEF-P11-05: Frontend TaskStateCard Consistency Verification
    # -------------------------------------------------------------------------
    def test_def_p11_05_frontend_task_state_card_includes_task_completed(self):
        """DEF-P11-05: Ensure TaskStateCard.jsx source file contains TASK_COMPLETED mapping."""
        with open(
            "frontend/src/components/TaskStateCard.jsx", "r", encoding="utf-8"
        ) as f:
            content = f.read()

        assert "'TASK_COMPLETED'" in content
        assert "state === 'COMPLETED' || state === 'TASK_COMPLETED'" in content
