"""
Unit tests for StepDependencyManager (Phase 6, Capability C, §5, §7).
Verifies DAG validation, cycle detection, topological sorting, ready-step calculation,
and cascading downstream blocks upon upstream failure.
"""

import pytest

from planner.dependency_manager import DependencyValidationError, StepDependencyManager
from planner.models import StepStatus, TaskStep


def test_valid_linear_dag():
    """Test standard linear dependency chain: step_1 -> step_2 -> step_3."""
    steps = [
        TaskStep(step_id="step_1", goal="Step 1", dependencies=[]),
        TaskStep(step_id="step_2", goal="Step 2", dependencies=["step_1"]),
        TaskStep(step_id="step_3", goal="Step 3", dependencies=["step_2"]),
    ]
    dm = StepDependencyManager()
    is_valid, err = dm.validate_dag(steps)
    assert is_valid is True
    assert err is None

    order = dm.get_topological_order(steps)
    assert [s.step_id for s in order] == ["step_1", "step_2", "step_3"]


def test_valid_branching_dag():
    """Test branching DAG: A -> B and A -> C."""
    steps = [
        TaskStep(step_id="step_1", goal="A", dependencies=[]),
        TaskStep(step_id="step_2", goal="B", dependencies=["step_1"]),
        TaskStep(step_id="step_3", goal="C", dependencies=["step_1"]),
    ]
    dm = StepDependencyManager()
    is_valid, err = dm.validate_dag(steps)  # noqa: RUF059
    assert is_valid is True
    order = dm.get_topological_order(steps)
    assert order[0].step_id == "step_1"


def test_circular_dependency_detected():
    """Test cycle detection: step_1 -> step_2 -> step_3 -> step_1."""
    steps = [
        TaskStep(step_id="step_1", goal="A", dependencies=["step_3"]),
        TaskStep(step_id="step_2", goal="B", dependencies=["step_1"]),
        TaskStep(step_id="step_3", goal="C", dependencies=["step_2"]),
    ]
    dm = StepDependencyManager()
    is_valid, err = dm.validate_dag(steps)
    assert is_valid is False
    assert "Circular dependency" in err

    with pytest.raises(DependencyValidationError):
        dm.get_topological_order(steps)


def test_self_dependency_detected():
    """Test self-dependency rejection: step_1 -> step_1."""
    steps = [
        TaskStep(step_id="step_1", goal="A", dependencies=["step_1"]),
    ]
    dm = StepDependencyManager()
    is_valid, err = dm.validate_dag(steps)
    assert is_valid is False
    assert "cannot depend on itself" in err


def test_missing_dependency_detected():
    """Test missing dependency reference rejection."""
    steps = [
        TaskStep(step_id="step_1", goal="A", dependencies=["non_existent_step"]),
    ]
    dm = StepDependencyManager()
    is_valid, err = dm.validate_dag(steps)
    assert is_valid is False
    assert "references non-existent dependency" in err


def test_duplicate_step_id_detected():
    """Test duplicate step_id rejection."""
    steps = [
        TaskStep(step_id="step_1", goal="A", dependencies=[]),
        TaskStep(step_id="step_1", goal="B", dependencies=[]),
    ]
    dm = StepDependencyManager()
    is_valid, err = dm.validate_dag(steps)
    assert is_valid is False
    assert "Duplicate step_id detected" in err


def test_ready_steps_calculation():
    """Test that steps are ready only when all prerequisites are COMPLETED."""
    s1 = TaskStep(
        step_id="step_1", goal="A", dependencies=[], status=StepStatus.PENDING
    )
    s2 = TaskStep(
        step_id="step_2", goal="B", dependencies=["step_1"], status=StepStatus.PENDING
    )
    s3 = TaskStep(
        step_id="step_3", goal="C", dependencies=["step_2"], status=StepStatus.PENDING
    )
    steps = [s1, s2, s3]

    dm = StepDependencyManager()
    ready = dm.get_ready_steps(steps)
    assert [s.step_id for s in ready] == ["step_1"]

    # Mark step_1 complete
    s1.status = StepStatus.COMPLETED
    ready = dm.get_ready_steps(steps)
    assert [s.step_id for s in ready] == ["step_2"]


def test_downstream_failure_cascades_blocks():
    """Test that when step_1 fails or is unverified, dependent step_2 and step_3 are blocked."""
    s1 = TaskStep(
        step_id="step_1", goal="A", dependencies=[], status=StepStatus.UNVERIFIED
    )
    s2 = TaskStep(
        step_id="step_2", goal="B", dependencies=["step_1"], status=StepStatus.PENDING
    )
    s3 = TaskStep(
        step_id="step_3", goal="C", dependencies=["step_2"], status=StepStatus.PENDING
    )
    steps = [s1, s2, s3]

    dm = StepDependencyManager()
    updated = dm.cascade_downstream_blocks(steps)

    assert updated[1].status == StepStatus.BLOCKED
    assert updated[2].status == StepStatus.BLOCKED
    assert "prerequisite" in updated[1].error.lower()
