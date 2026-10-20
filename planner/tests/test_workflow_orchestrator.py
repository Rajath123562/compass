import asyncio
import tempfile

import pytest

from planner.workflow.dag import DAGEngine
from planner.workflow.models import WorkflowGraph, WorkflowNode, WorkflowState
from planner.workflow.orchestrator import WorkflowOrchestrator
from planner.workflow.recovery import CheckpointManager
from planner.workflow.scheduler import LockManager


@pytest.fixture
def orchestrator():
    lm = LockManager()
    dag = DAGEngine()
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CheckpointManager(secret_key=b"test", wal_dir=tmpdir)
        yield WorkflowOrchestrator(dag, lm, cm)


@pytest.mark.asyncio
async def test_orchestrator_end_to_end(orchestrator):
    results = []

    async def dummy_action(params):
        await asyncio.sleep(0.01)
        results.append(params.get("val"))

    orchestrator.register_action("dummy", dummy_action)

    n1 = WorkflowNode(id="A", action="dummy", params={"val": 1})
    n2 = WorkflowNode(id="B", action="dummy", depends_on=["A"], params={"val": 2})

    graph = WorkflowGraph(workflow_id="wf1", nodes={"A": n1, "B": n2})
    orchestrator.submit_workflow(graph)

    await orchestrator.start_workflow("wf1")

    assert graph.state == WorkflowState.COMPLETED
    assert results == [1, 2]


@pytest.mark.asyncio
async def test_universal_stop(orchestrator):
    async def slow_action(params):
        await asyncio.sleep(0.5)

    orchestrator.register_action("slow", slow_action)

    n1 = WorkflowNode(id="A", action="slow")
    graph = WorkflowGraph(workflow_id="wf2", nodes={"A": n1})
    orchestrator.submit_workflow(graph)

    # Start in background
    task = asyncio.create_task(orchestrator.start_workflow("wf2"))

    # Wait briefly then stop
    await asyncio.sleep(0.05)
    orchestrator.stop_workflow("wf2")

    await task

    assert graph.state == WorkflowState.CANCELLED
    # Node might be still running in background, but the workflow generation fenced it
    assert graph.generation == 1


def test_workflow_orchestrator_identity():
    import planner.workflow.orchestrator as pkg
    import planner.workflow_orchestrator as flat

    assert flat.WorkflowOrchestrator is pkg.WorkflowOrchestrator

