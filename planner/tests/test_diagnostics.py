import pytest

from backend.app.database import db
from planner.reliability.diagnostics import emit_incident
from planner.workflow.dag import DAGEngine
from planner.workflow.models import (
    NodeState,
    WorkflowGraph,
    WorkflowNode,
    WorkflowState,
)
from planner.workflow.orchestrator import WorkflowOrchestrator
from planner.workflow.recovery import CheckpointManager
from planner.workflow.scheduler import LockManager


def test_emit_incident_db():
    try:
        1 / 0  # noqa: B018
    except Exception as e:  # noqa: BLE001
        incident_id = emit_incident(
            workflow_id="wf_1", node_id="node_1", exception=e, severity="WARNING"
        )

    inc = db.get_incident(incident_id)
    assert inc is not None
    assert inc["workflow_id"] == "wf_1"
    assert inc["node_id"] == "node_1"
    assert inc["severity"] == "WARNING"
    assert "ZeroDivisionError" in inc["description"]


@pytest.mark.asyncio
async def test_orchestrator_emits_incident_on_failure(tmp_path):
    dag = DAGEngine()
    lm = LockManager()
    cm = CheckpointManager(b"supersecretkey", str(tmp_path / "wal"))
    orchestrator = WorkflowOrchestrator(dag, lm, cm)

    # Action that fails
    def fail_action(params):
        raise ValueError("Simulated failure")

    orchestrator.register_action("fail", fail_action)

    node = WorkflowNode(id="n1", action="fail")
    import uuid

    wf_id = f"wf_test_inc_{uuid.uuid4().hex[:8]}"
    graph = WorkflowGraph(workflow_id=wf_id, nodes={"n1": node})

    orchestrator.submit_workflow(graph)

    # It should not crash the loop, but gracefully fail the node and emit incident
    await orchestrator.start_workflow(wf_id)

    assert graph.state == WorkflowState.FAILED
    assert node.state == NodeState.FAILED

    # Check DB
    incidents = db.list_incidents()
    wf_incidents = [i for i in incidents if i["workflow_id"] == wf_id]
    assert len(wf_incidents) == 1
    assert wf_incidents[0]["node_id"] == "n1"
    assert "Simulated failure" in wf_incidents[0]["description"]
