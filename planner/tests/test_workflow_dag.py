import pytest

from planner.workflow.dag import DAGEngine, DAGValidationError
from planner.workflow.models import NodeState, WorkflowGraph, WorkflowNode


def test_dag_validation_success():
    engine = DAGEngine()

    n1 = WorkflowNode(id="A", action="noop")
    n2 = WorkflowNode(id="B", action="noop", depends_on=["A"])
    n3 = WorkflowNode(id="C", action="noop", depends_on=["A"])
    n4 = WorkflowNode(id="D", action="noop", depends_on=["B", "C"])

    graph = WorkflowGraph(workflow_id="wf1", nodes={"A": n1, "B": n2, "C": n3, "D": n4})

    sorted_nodes = engine.validate_and_sort(graph)
    assert len(sorted_nodes) == 4
    assert sorted_nodes[0] == "A"
    assert sorted_nodes[-1] == "D"


def test_dag_validation_cycle():
    engine = DAGEngine()

    n1 = WorkflowNode(id="A", action="noop", depends_on=["C"])
    n2 = WorkflowNode(id="B", action="noop", depends_on=["A"])
    n3 = WorkflowNode(id="C", action="noop", depends_on=["B"])

    graph = WorkflowGraph(workflow_id="wf1", nodes={"A": n1, "B": n2, "C": n3})

    with pytest.raises(DAGValidationError, match="Cycle detected"):
        engine.validate_and_sort(graph)


def test_dag_validation_missing_dep():
    engine = DAGEngine()
    n1 = WorkflowNode(id="A", action="noop", depends_on=["Z"])
    graph = WorkflowGraph(workflow_id="wf1", nodes={"A": n1})

    with pytest.raises(DAGValidationError, match="missing node 'Z'"):
        engine.validate_and_sort(graph)


def test_get_ready_nodes():
    engine = DAGEngine()

    n1 = WorkflowNode(id="A", action="noop", state=NodeState.COMPLETED)
    n2 = WorkflowNode(
        id="B", action="noop", depends_on=["A"], state=NodeState.PENDING, priority=10
    )
    n3 = WorkflowNode(
        id="C", action="noop", depends_on=["A"], state=NodeState.PENDING, priority=5
    )
    n4 = WorkflowNode(id="D", action="noop", depends_on=["B"], state=NodeState.PENDING)

    graph = WorkflowGraph(workflow_id="wf1", nodes={"A": n1, "B": n2, "C": n3, "D": n4})

    ready = engine.get_ready_nodes(graph)
    assert len(ready) == 2
    # Check priority sorting
    assert ready[0].id == "B"
    assert ready[1].id == "C"


def test_max_depth_exceeded():
    engine = DAGEngine(max_depth=3)

    nodes = {}
    for i in range(5):
        deps = [f"N{i - 1}"] if i > 0 else []
        nodes[f"N{i}"] = WorkflowNode(id=f"N{i}", action="noop", depends_on=deps)

    graph = WorkflowGraph(workflow_id="wf1", nodes=nodes)

    with pytest.raises(DAGValidationError, match="Max depth exceeded"):
        engine.validate_and_sort(graph)


def test_workflow_dag_identity():
    import planner.workflow.dag as pkg
    import planner.workflow_dag as flat

    assert flat.DAGEngine is pkg.DAGEngine
    assert flat.DAGValidationError is pkg.DAGValidationError
    assert flat.WorkflowDAGValidator is pkg.WorkflowDAGValidator

