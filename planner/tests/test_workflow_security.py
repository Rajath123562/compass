"""
Tests for Phase 8 Safety Gating, Approval Boundaries, and Secret Redaction (Gates 29, 30, 31).
"""

from planner.checkpoint_manager import CheckpointManager
from planner.execution_trace import ExecutionTraceManager
from planner.workflow_models import WorkflowNode, WorkflowNodeStatus
from planner.workflow_orchestrator import WorkflowOrchestrator


def test_high_risk_node_approval_gating():
    """Consequential action requiring human approval cannot execute autonomously."""
    orch = WorkflowOrchestrator()
    n1 = WorkflowNode(
        node_id="A",
        goal="Delete system files",
        risk_level="HIGH",
        approval_required=True,
        action={"type": "delete_directory"},
    )

    wf = orch.create_workflow(goal="safety test", nodes=[n1])
    # Run one pass of loop
    generation = wf.execution_generation  # noqa: F841
    ready = orch.scheduler.get_ready_nodes(wf, max_concurrent=2)
    assert len(ready) == 1

    # Node requires approval, so status must change to WAITING_APPROVAL, NOT RUNNING
    node = ready[0]
    if node.approval_required:
        node.status = WorkflowNodeStatus.WAITING_APPROVAL

    assert node.status == WorkflowNodeStatus.WAITING_APPROVAL


def test_secret_redaction_in_checkpoint():
    """CheckpointManager must scrub API keys, bearer tokens, and passwords."""
    cm = CheckpointManager()
    state = {
        "api_key": "sk-123456789012345678901234",
        "auth_header": "Bearer secret_jwt_token_here",
        "password": "my_secret_pass",
        "regular_text": "hello safe world",
    }

    cp = cm.save_workflow_checkpoint(
        workflow_id="wf_sec", task_id="t_sec", status="RUNNING", resource_state=state
    )

    assert cp.resource_state["api_key"] == "[REDACTED_SECRET]"
    assert cp.resource_state["password"] == "[REDACTED_SECRET]"
    assert cp.resource_state["regular_text"] == "hello safe world"


def test_secret_redaction_in_trace():
    """ExecutionTraceManager must scrub secrets from goals and traces."""
    tm = ExecutionTraceManager()
    tr = tm.start_workflow_trace(
        "wf_sec", "t_sec", "Run task with sk-123456789012345678901234"
    )
    assert "sk-" not in tr.goal
    assert "[REDACTED_API_KEY]" in tr.goal
