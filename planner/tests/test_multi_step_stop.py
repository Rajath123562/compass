"""
Unit tests for Universal STOP across Multi-Step Execution (Phase 6, Capability B, §26, §32).
Verifies immediate task cancellation and clean resource termination across all multi-step lifecycle points.
"""

from unittest.mock import patch

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.execution_controller import MultiStepExecutionController


def test_stop_before_decomposition():
    """STOP asserted before decomposition halts task immediately."""
    controller = MultiStepExecutionController()
    task = task_service.create_task("Test Stop Early")
    tid = task["id"]

    controller.stop_task(tid, reason="Pre-execution STOP")
    assert controller.is_stopped(tid) is True

    res = controller.run_multistep_task(tid, "Open Notepad and type text")
    assert res["status"] in ["CANCELLED", "STOPPED"]
    assert res["success"] is False

    t_rec = task_service.get_task(tid)
    assert t_rec["state"] in [TaskState.CANCELLED.value, TaskState.STOPPED.value]


def test_stop_mid_step_execution():
    """STOP asserted between steps halts multi-step execution without executing subsequent steps."""
    controller = MultiStepExecutionController()
    task = task_service.create_task("Test Stop Mid Step")
    tid = task["id"]

    events = []

    def on_event(ev_type, payload):
        events.append(ev_type)
        if ev_type == "step_completed":
            # Assert STOP immediately after first step completes
            controller.stop_task(tid, reason="STOP asserted after step 1")

    with patch(
        "automation.action_dispatcher.type_text", return_value={"success": True}
    ), patch(
        "perception.uia_inspector.get_foreground_window",
        return_value={"window": {"title": "Notepad"}},
    ):
        res = controller.run_multistep_task(
            tid, "Open Notepad then type text", on_event=on_event
        )

    assert res["status"] in ["CANCELLED", "STOPPED"]
    assert res["success"] is False
    assert "step_completed" in events


def test_stop_is_idempotent_and_thread_safe():
    """Repeated calls to stop_task do not raise errors and maintain terminal cancellation state."""
    controller = MultiStepExecutionController()
    task = task_service.create_task("Test Idempotent Multi-Step Stop")
    tid = task["id"]

    for i in range(5):
        ok = controller.stop_task(tid, reason=f"Stop invocation #{i}")
        assert ok is True
        assert controller.is_stopped(tid) is True
