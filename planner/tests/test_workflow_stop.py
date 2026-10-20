"""
Tests for Universal STOP and Generation Fencing (Gate 25).
"""

import time

from planner.workflow_models import WorkflowNode, WorkflowStatus
from planner.workflow_orchestrator import WorkflowOrchestrator


def test_universal_stop_transitions_and_fencing():
    orch = WorkflowOrchestrator()

    # Create long-running nodes
    def slow_executor(node: WorkflowNode):
        for _ in range(50):
            time.sleep(0.05)
        return True, None, {}

    orch.custom_node_executor = slow_executor

    n1 = WorkflowNode(node_id="A", goal="Slow step")
    wf = orch.create_workflow(goal="stop test", nodes=[n1])
    assert wf.execution_generation == 1

    # Start in background
    orch.start_workflow(wf.workflow_id, run_in_background=True)
    time.sleep(0.1)

    # Issue STOP
    stopped = orch.stop_workflow(wf.workflow_id, reason="Emergency user abort")
    assert stopped

    refreshed = orch.get_workflow(wf.workflow_id)
    assert refreshed.status == WorkflowStatus.STOPPED
    # Generation must be incremented to fence stale loop
    assert refreshed.execution_generation >= 2

    # Checkpoint should exist and be valid
    ok, cp, err = orch.checkpoint_manager.load_workflow_checkpoint(wf.workflow_id)  # noqa: RUF059
    assert ok
    assert cp.status == "STOPPED"
