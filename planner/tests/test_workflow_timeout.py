"""
Tests for Phase 8 Workflow Deadlines and Timeouts (Gate 20).
"""

import time

from planner.workflow_models import ResourceBudget, WorkflowNode, WorkflowStatus
from planner.workflow_orchestrator import WorkflowOrchestrator


def test_workflow_deadline_timeout():
    orch = WorkflowOrchestrator()

    def slow_executor(node: WorkflowNode):
        time.sleep(1.5)
        return True, None, {}

    orch.custom_node_executor = slow_executor

    n1 = WorkflowNode(node_id="A", goal="Slow step")
    # Set deadline of 0.5 seconds from now
    budget = ResourceBudget(max_duration_s=10.0)
    wf = orch.create_workflow(
        goal="timeout test",
        nodes=[n1],
        resource_budget=budget,
        deadline=time.time() + 0.5,
    )

    orch.start_workflow(wf.workflow_id, run_in_background=False)
    refreshed = orch.get_workflow(wf.workflow_id)
    assert refreshed.status == WorkflowStatus.TIMED_OUT
