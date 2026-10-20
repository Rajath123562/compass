"""
Tests for Phase 8 Node Retry Policies and Exhaustion (Gate 19).
"""

from planner.workflow_models import (
    RetryPolicy,
    WorkflowNode,
    WorkflowNodeStatus,
    WorkflowStatus,
)
from planner.workflow_orchestrator import WorkflowOrchestrator


def test_transient_retry_succeeds():
    orch = WorkflowOrchestrator()
    attempts = {"count": 0}

    def failing_first_executor(node: WorkflowNode):
        attempts["count"] += 1
        if attempts["count"] < 2:
            return False, "PROVIDER_TIMEOUT", None
        return True, None, {"output": "recovered"}

    orch.custom_node_executor = failing_first_executor

    n1 = WorkflowNode(
        node_id="A",
        goal="Retryable step",
        retry_policy=RetryPolicy(
            max_attempts=3, min_backoff_ms=50.0, max_backoff_ms=200.0
        ),
    )

    wf = orch.create_workflow(goal="retry success test", nodes=[n1])
    orch.start_workflow(wf.workflow_id, run_in_background=False)

    refreshed = orch.get_workflow(wf.workflow_id)
    assert refreshed.status == WorkflowStatus.COMPLETED
    assert attempts["count"] == 2
    assert refreshed.nodes[0].attempt_count == 2


def test_retry_exhaustion_cascades_failure():
    orch = WorkflowOrchestrator()
    attempts = {"count": 0}

    def always_fail_executor(node: WorkflowNode):
        attempts["count"] += 1
        return False, "TIMEOUT", None

    orch.custom_node_executor = always_fail_executor

    n1 = WorkflowNode(
        node_id="A",
        goal="Always failing step",
        retry_policy=RetryPolicy(
            max_attempts=2, min_backoff_ms=50.0, max_backoff_ms=100.0
        ),
    )
    n2 = WorkflowNode(node_id="B", goal="Dependent step", dependencies=["A"])

    wf = orch.create_workflow(goal="retry exhaust test", nodes=[n1, n2])
    orch.start_workflow(wf.workflow_id, run_in_background=False)

    refreshed = orch.get_workflow(wf.workflow_id)
    assert refreshed.status == WorkflowStatus.FAILED
    assert refreshed.nodes[0].status == WorkflowNodeStatus.FAILED
    assert refreshed.nodes[0].attempt_count == 2
    # B was blocked by dependency cascade
    assert refreshed.nodes[1].status == WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY
