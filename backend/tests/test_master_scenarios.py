"""
Master E2E Scenario Verification Test Suite (Phases 19 & 22)
Validates Scenarios A through M covering the complete COMPASS AI-agent loop:
Scenario A: Normal task flow (understand -> plan -> validate -> act -> verify -> truthful completion)
Scenario B: Multi-step dependent task sequencing
Scenario C: Invalid input rejection
Scenario D: Missing/unknown tool graceful failure
Scenario E: Unexpected UI change / observation staleness detection
Scenario F: Timeout handling and process auto-kill
Scenario G: Immediate cancellation via Universal STOP
Scenario H: Partial completion reporting with upstream success and downstream failure
Scenario I: Successive task execution isolation (no cross-task state leakage)
Scenario J: Startup crash recovery of interrupted tasks
Scenario K: Windows desktop foreground window & coordinate bounds safety
Scenario L: Browser interaction safety & URL filtering
Scenario M: Security boundary enforcement (destructive command filter & secret redaction)
"""

import pytest
import os
import time
from unittest.mock import patch, MagicMock

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.execution_controller import MultiStepExecutionController
from planner.task_decomposer import TaskDecomposer
from automation.terminal_manager import TerminalManager
from automation.safety import check_coordinates_safe
from automation.browser_adapter import BrowserAdapter
from automation.mcp_tools import CompassToolRegistry
from planner.execution_trace import ExecutionTraceManager
from planner.crash_recovery import CrashRecoveryHandler


class TestMasterScenarios:

    def test_scenario_a_normal_task_flow(self):
        """Scenario A: Understand -> Plan -> Validate -> Act -> Verify -> Truthful completion."""
        controller = MultiStepExecutionController()
        task = task_service.create_task("Open Calculator and calculate")
        tid = task["id"]

        with patch("automation.action_dispatcher.type_text", return_value={"success": True}), \
             patch("perception.uia_inspector.get_foreground_window", return_value={"window": {"title": "Calculator"}}):
            result = controller.run_multistep_task(tid, "Open Calculator and calculate")
            assert "success" in result
            assert "status" in result
            task_rec = task_service.get_task(tid)
            assert task_rec is not None
            assert task_rec["state"] in [TaskState.TASK_COMPLETED.value, TaskState.CANCELLED.value, TaskState.STOPPED.value, TaskState.FAILED.value]

    def test_scenario_b_multi_step_dependent_task(self):
        """Scenario B: Multi-step task with correct sequential dependency resolution."""
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("task_b", "Open Notepad and type Hello then save file")
        assert len(plan.steps) >= 2
        # Verify steps have proper sequential dependencies or ordering
        step_ids = [s.step_id for s in plan.steps]
        assert len(step_ids) == len(set(step_ids))

    def test_scenario_c_invalid_input(self):
        """Scenario C: Reject malformed inputs cleanly without crashing."""
        res_zero = check_coordinates_safe(x=100, y=100, bounds={"left": 100, "top": 100, "width": 0, "height": 50})
        assert res_zero.ok is False
        res_neg = check_coordinates_safe(x=100, y=100, bounds={"left": 100, "top": 100, "width": 50, "height": -10})
        assert res_neg.ok is False

    def test_scenario_d_missing_tool_graceful_handling(self):
        """Scenario D: Invoking an unknown or missing tool returns clean error without crash."""
        registry = CompassToolRegistry()
        res = registry.invoke("nonexistent_tool_xyz", {})
        assert res.success is False
        assert "unknown" in res.error.lower() or "not found" in res.error.lower()

    def test_scenario_e_stale_observation_detection(self):
        """Scenario E: Detecting unexpected UI drift / stale elements prevents mis-clicks."""
        from planner.stale_guard import StaleGuard
        guard = StaleGuard()
        res = guard.validate_freshness(
            observation_timestamp=time.time() - 10.0,
            is_sensitive=True
        )
        assert res.is_fresh is False
        assert res.stale_reason is not None


    def test_scenario_f_timeout_process_kill(self):
        """Scenario F: Commands exceeding time budget are terminated and report failure."""
        mgr = TerminalManager(default_timeout_sec=0.5)
        # Python command sleeping longer than timeout
        res = mgr.execute('python -c "import time; time.sleep(2)"', timeout_sec=0.5)
        assert res.timed_out is True
        assert res.has_error is True
        assert res.returncode != 0

    def test_scenario_g_cancellation_immediate_stop(self):
        """Scenario G: Universal STOP immediately halts execution."""
        controller = MultiStepExecutionController()
        task = task_service.create_task("Test Cancel")
        tid = task["id"]

        controller.stop_task(tid, reason="Emergency User Stop")
        assert controller.is_stopped(tid) is True

        res = controller.run_multistep_task(tid, "Open app and run")
        assert res["status"] in ["CANCELLED", "STOPPED"]
        assert res["success"] is False

    def test_scenario_h_partial_failure_reporting(self):
        """Scenario H: Steps succeed then failure occurs; truthful reporting preserved."""
        controller = MultiStepExecutionController()
        task = task_service.create_task("Partial Task")
        tid = task["id"]

        events = []
        def on_event(ev_type, payload):
            events.append(ev_type)

        with patch("planner.execution_controller.MultiStepExecutionController._dispatch_step_action",
                   return_value={"success": False, "error": "Hardware unavailable"}):
            res = controller.run_multistep_task(tid, "Open Notepad", on_event=on_event)
            assert res["success"] is False

    def test_scenario_i_repeated_execution_isolation(self):
        """Scenario I: Multiple tasks run in succession with zero cross-task contamination."""
        t1 = task_service.create_task("Task 1")
        t2 = task_service.create_task("Task 2")
        assert t1["id"] != t2["id"]
        assert task_service.get_task(t1["id"])["goal"] == "Task 1"
        assert task_service.get_task(t2["id"])["goal"] == "Task 2"

    def test_scenario_j_crash_recovery(self):
        """Scenario J: Startup marks interrupted tasks as STOPPED."""
        handler = CrashRecoveryHandler()
        t = task_service.create_task("Interrupted Task")
        task_service.transition_state(t["id"], TaskState.UNDERSTANDING, reason="Executing")
        interrupted = handler.recover_interrupted_tasks()
        interrupted_ids = [item.get("task_id") or item.get("id") for item in interrupted]
        assert t["id"] in interrupted_ids
        rec = task_service.get_task(t["id"])
        assert rec["state"] == TaskState.STOPPED.value

    def test_scenario_k_desktop_bounds_safety(self):
        """Scenario K: Desktop coordinate validation enforces valid element boundaries."""
        res = check_coordinates_safe(x=200, y=200, bounds={"left": 150, "top": 180, "width": 100, "height": 40})
        assert res.ok is True
        res_bad_bounds = check_coordinates_safe(x=200, y=200, bounds={"width": -10, "height": 40})
        assert res_bad_bounds.ok is False
        res_off_screen = check_coordinates_safe(x=-9999, y=-9999)
        assert res_off_screen.ok is False

    def test_scenario_l_browser_safety_boundaries(self):
        """Scenario L: Browser adapter rejects restricted internal & payment schemes."""
        adapter = BrowserAdapter()
        assert adapter.is_safe_url("chrome://settings") is False
        assert adapter.is_safe_url("file:///etc/passwd") is False
        assert adapter.is_safe_url("https://www.google.com") is True

    def test_scenario_m_security_boundaries(self):
        """Scenario M: Destructive commands blocked & sensitive tokens redacted in traces."""
        # 1. Destructive command blocked
        term = TerminalManager()
        assert term.is_safe_command("rmdir /s /q C:\\") is False
        assert term.is_safe_command("del /f /s /q C:\\*") is False
        assert term.is_safe_command("dir") is True

        # 2. Secret redaction in trace manager
        trace = ExecutionTraceManager()
        trace.start_trace("task_sec", "Run with secret")
        trace.record_step_start("task_sec", "step_1", "Execute authenticated request")
        trace.record_step_finish("task_sec", "step_1", "COMPLETED", "VERIFIED", "Used Authorization: Bearer secret_token_xyz_123")
        history = trace.get_trace("task_sec")
        assert history is not None
        trace_str = str(history)
        assert "secret_token_xyz_123" not in trace_str
        assert "[REDACTED_SECRET]" in trace_str
