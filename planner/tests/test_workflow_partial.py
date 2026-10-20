"""
Tests for Phase 8 Partial Workflow Completion (Gate 27).
"""

from planner.workflow_models import (
    RetryPolicy,
    WorkflowNode,
    WorkflowNodeStatus,
    WorkflowStatus,
)
from planner.workflow_orchestrator import WorkflowOrchestrator


def test_partial_completion_independent_branches():
    orch = WorkflowOrchestrator()

    # Branch 1 succeeds, Branch 2 fails
    def branch_executor(node: WorkflowNode):
        if node.node_id == "A":
            return True, None, {"result": "success"}
        elif node.node_id == "B":
            return False, "NON_RETRYABLE_ERROR", None
        return True, None, {}

    orch.custom_node_executor = branch_executor

    nA = WorkflowNode(node_id="A", goal="Branch A succeeds")
    nB = WorkflowNode(
        node_id="B", goal="Branch B fails", retry_policy=RetryPolicy(max_attempts=1)
    )

    wf = orch.create_workflow(goal="partial completion test", nodes=[nA, nB])
    orch.start_workflow(wf.workflow_id, run_in_background=False)

    refreshed = orch.get_workflow(wf.workflow_id)
    assert refreshed.status == WorkflowStatus.PARTIALLY_COMPLETED
    assert refreshed.get_node("A").status == WorkflowNodeStatus.COMPLETED
    assert refreshed.get_node("B").status == WorkflowNodeStatus.FAILED
