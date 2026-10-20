"""
Tests for Workflow Pause and Resume Lifecycle (Gate 26).
"""

import time

from planner.workflow_models import WorkflowNode, WorkflowStatus
from planner.workflow_orchestrator import WorkflowOrchestrator


def test_pause_and_resume_lifecycle():
    orch = WorkflowOrchestrator()

    # Step that pauses after first action
    n1 = WorkflowNode(node_id="A", goal="Step 1", action={"type": "noop"})
    n2 = WorkflowNode(
        node_id="B", goal="Step 2", dependencies=["A"], action={"type": "noop"}
    )

    wf = orch.create_workflow(goal="pause resume test", nodes=[n1, n2])
    orch.start_workflow(wf.workflow_id, run_in_background=True)

    # Pause
    time.sleep(0.05)
    paused = orch.pause_workflow(wf.workflow_id)
    assert paused
    assert orch.get_workflow(wf.workflow_id).status == WorkflowStatus.PAUSED

    # Resume
    resumed = orch.resume_workflow(wf.workflow_id)
    assert resumed
    assert orch.get_workflow(wf.workflow_id).status in (
        WorkflowStatus.RUNNING,
        WorkflowStatus.COMPLETED,
    )

    # Let complete
    time.sleep(0.5)
    final_wf = orch.get_workflow(wf.workflow_id)
    assert final_wf.status == WorkflowStatus.COMPLETED


def test_pause_invalid_state():
    orch = WorkflowOrchestrator()
    n1 = WorkflowNode(node_id="A", goal="Step 1")
    wf = orch.create_workflow(goal="invalid pause test", nodes=[n1])
    # Workflow in READY state cannot be paused
    assert not orch.pause_workflow(wf.workflow_id)
