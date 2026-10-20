"""
Tests for Phase 8 Concurrency Control and Deadlock Freedom (Gates 17, 39).
"""

import threading
import time

from planner.workflow_models import WorkflowNode, WorkflowStatus
from planner.workflow_orchestrator import WorkflowOrchestrator
from planner.workflow_scheduler import ReadyNodeScheduler, ResourceLockManager


def test_deadlock_free_lock_ordering():
    """Two threads trying to acquire conflicting locks in opposite orders."""
    lm = ResourceLockManager()
    errors = []

    def worker_A():
        try:
            # Request [Y, X]
            ok = lm.acquire_locks(["lock:Y", "lock:X"], "worker_A", timeout_s=3.0)
            if ok:
                time.sleep(0.05)
                lm.release_locks(["lock:Y", "lock:X"], "worker_A")
            else:
                errors.append("worker_A timed out")
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    def worker_B():
        try:
            # Request [X, Y]
            ok = lm.acquire_locks(["lock:X", "lock:Y"], "worker_B", timeout_s=3.0)
            if ok:
                time.sleep(0.05)
                lm.release_locks(["lock:X", "lock:Y"], "worker_B")
            else:
                errors.append("worker_B timed out")
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    t1 = threading.Thread(target=worker_A)
    t2 = threading.Thread(target=worker_B)
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert not t1.is_alive()
    assert not t2.is_alive()
    assert len(errors) == 0, f"Deadlock or error occurred: {errors}"


def test_concurrent_independent_nodes():
    """Parallel execution of two independent nodes with different locks."""
    orch = WorkflowOrchestrator()
    execution_times = {}

    def custom_executor(node: WorkflowNode):
        execution_times[node.node_id] = time.time()
        time.sleep(0.2)
        return True, None, {"output": f"done {node.node_id}"}

    orch.custom_node_executor = custom_executor

    # Two nodes that do NOT contend for UI foreground
    n1 = WorkflowNode(
        node_id="read_file1",
        goal="Read file 1",
        action={"type": "read_file", "path": "dummy1"},
        resource_requirements={"requires_ui": False},
    )
    n2 = WorkflowNode(
        node_id="read_file2",
        goal="Read file 2",
        action={"type": "read_file", "path": "dummy2"},
        resource_requirements={"requires_ui": False},
    )

    wf = orch.create_workflow(goal="concurrent test", nodes=[n1, n2])
    orch.start_workflow(wf.workflow_id, run_in_background=False)

    refreshed = orch.get_workflow(wf.workflow_id)
    assert refreshed.status == WorkflowStatus.COMPLETED
    assert len(execution_times) == 2


def test_serialized_ui_actions():
    """UI actions contending for UI foreground lock must be serialized."""
    lm = ResourceLockManager()
    scheduler = ReadyNodeScheduler(lm)

    n1 = WorkflowNode(
        node_id="click1",
        goal="Click button",
        action={"type": "click", "application": "app1.exe"},
        resource_requirements={"requires_ui": True},
    )
    n2 = WorkflowNode(
        node_id="click2",
        goal="Click other button",
        action={"type": "click", "application": "app2.exe"},
        resource_requirements={"requires_ui": True},
    )

    # Acquire UI foreground lock for n1
    locks1 = scheduler.compute_required_locks(n1)
    assert ReadyNodeScheduler.UI_FOREGROUND_LOCK in locks1
    lm.acquire_locks(locks1, "holder1")

    # n2 cannot dispatch while n1 holds UI lock
    can_disp, conflicts = scheduler.can_dispatch_node(n2)
    assert not can_disp
    assert ReadyNodeScheduler.UI_FOREGROUND_LOCK in conflicts

    lm.release_locks(locks1, "holder1")
    can_disp_after, _ = scheduler.can_dispatch_node(n2)
    assert can_disp_after
