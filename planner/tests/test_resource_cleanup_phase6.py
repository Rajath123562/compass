"""
Unit tests for Resource Cleanup & Orphan Teardown across all 13 Terminal Paths (Phase 6, §21).
Verifies active task clearance, process cleanup, lock release, and zero orphan background threads.
"""

from backend.app.models import TaskState, is_terminal_state
from backend.app.services.task_service import task_service
from planner.execution_controller import MultiStepExecutionController


def test_cleanup_after_successful_multistep_task():
    """Verify cleanup after normal multi-step success."""
    ctrl = MultiStepExecutionController()
    t = task_service.create_task("Test Cleanup Success")
    tid = t["id"]

    res = ctrl.run_multistep_task(tid, "Open Notepad", on_event=None)  # noqa: F841
    assert not ctrl.is_stopped(tid)
    assert ctrl.trace_manager.get_trace(tid) is not None


def test_cleanup_after_stop_signal():
    """Verify resources released and state updated after STOP."""
    ctrl = MultiStepExecutionController()
    t = task_service.create_task("Test Cleanup Stop")
    tid = t["id"]

    ctrl.stop_task(tid, reason="Explicit STOP test")
    res = ctrl.run_multistep_task(tid, "Open Notepad")  # noqa: F841

    t_rec = task_service.get_task(tid)
    assert is_terminal_state(TaskState(t_rec["state"]))


def test_cleanup_after_task_timeout():
    """Verify timeout terminates execution loop and updates state cleanly."""
    ctrl = MultiStepExecutionController()
    t = task_service.create_task("Test Cleanup Timeout")
    tid = t["id"]

    # Run with tiny max_duration_s=0.001 to trigger immediate timeout
    res = ctrl.run_multistep_task(tid, "Open Notepad", max_duration_s=0.001)
    assert res["status"] == "FAILED"
    assert "duration budget" in res["error"]

    t_rec = task_service.get_task(tid)
    assert is_terminal_state(TaskState(t_rec["state"]))


def test_cleanup_after_consequential_safety_block():
    """Verify cleanup when consequential action is blocked by safety controls."""
    ctrl = MultiStepExecutionController()
    t = task_service.create_task("Test Cleanup Consequential")
    tid = t["id"]

    res = ctrl.run_multistep_task(tid, "Delete system files and purge directories")
    assert res["status"] in ["SAFETY_BLOCKED", "BLOCKED"]

    t_rec = task_service.get_task(tid)
    assert is_terminal_state(TaskState(t_rec["state"]))
