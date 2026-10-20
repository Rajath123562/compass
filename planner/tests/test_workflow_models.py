"""
Tests for Phase 8 Workflow Data Models and State Machines (Gate 10).
"""

import pytest
from pydantic import ValidationError

from planner.workflow_models import (
    ResourceBudget,
    RetryPolicy,
    Workflow,
    WorkflowNodeStatus,
    WorkflowStatus,
    validate_node_transition,
    validate_workflow_transition,
)


def test_workflow_status_count():
    assert len(WorkflowStatus) == 18


def test_node_status_count():
    assert len(WorkflowNodeStatus) == 13


def test_workflow_legal_transitions():
    assert validate_workflow_transition(
        WorkflowStatus.CREATED, WorkflowStatus.VALIDATING
    )
    assert validate_workflow_transition(WorkflowStatus.VALIDATING, WorkflowStatus.READY)
    assert validate_workflow_transition(WorkflowStatus.READY, WorkflowStatus.RUNNING)
    assert validate_workflow_transition(WorkflowStatus.RUNNING, WorkflowStatus.PAUSED)
    assert validate_workflow_transition(WorkflowStatus.PAUSED, WorkflowStatus.RUNNING)
    assert validate_workflow_transition(
        WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED
    )
    assert validate_workflow_transition(WorkflowStatus.RUNNING, WorkflowStatus.FAILED)
    assert validate_workflow_transition(WorkflowStatus.RUNNING, WorkflowStatus.STOPPED)


def test_workflow_illegal_transitions():
    # Direct jump from CREATED to COMPLETED
    assert not validate_workflow_transition(
        WorkflowStatus.CREATED, WorkflowStatus.COMPLETED
    )
    # Self-transition
    assert not validate_workflow_transition(
        WorkflowStatus.RUNNING, WorkflowStatus.RUNNING
    )
    # COMPLETED is terminal (no forward transitions)
    assert not validate_workflow_transition(
        WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING
    )


def test_node_legal_transitions():
    assert validate_node_transition(
        WorkflowNodeStatus.PENDING, WorkflowNodeStatus.READY
    )
    assert validate_node_transition(
        WorkflowNodeStatus.READY, WorkflowNodeStatus.RUNNING
    )
    assert validate_node_transition(
        WorkflowNodeStatus.RUNNING, WorkflowNodeStatus.COMPLETED
    )
    assert validate_node_transition(
        WorkflowNodeStatus.RUNNING, WorkflowNodeStatus.FAILED
    )
    assert validate_node_transition(
        WorkflowNodeStatus.FAILED, WorkflowNodeStatus.RETRYING
    )
    assert validate_node_transition(
        WorkflowNodeStatus.RETRYING, WorkflowNodeStatus.READY
    )


def test_node_illegal_transitions():
    assert not validate_node_transition(
        WorkflowNodeStatus.PENDING, WorkflowNodeStatus.COMPLETED
    )
    assert not validate_node_transition(
        WorkflowNodeStatus.COMPLETED, WorkflowNodeStatus.RUNNING
    )


def test_resource_budget_defaults_and_validation():
    budget = ResourceBudget()
    assert budget.max_duration_s == 600.0
    assert budget.max_nodes == 30
    assert budget.max_concurrent_nodes == 2

    with pytest.raises(ValidationError):
        ResourceBudget(max_duration_s=5.0)  # ge=10.0


def test_retry_policy_logic():
    policy = RetryPolicy(max_attempts=3, min_backoff_ms=500.0, max_backoff_ms=2000.0)
    assert policy.is_retryable("PROVIDER_TIMEOUT occurred")
    assert not policy.is_retryable("SAFETY_BLOCKED action")
    bo = policy.get_backoff_seconds(1)
    assert 0.5 <= bo <= 2.0


def test_workflow_generation_fencing():
    wf = Workflow(goal="test fence", nodes=[])
    assert wf.execution_generation == 1
    new_gen = wf.increment_generation()
    assert new_gen == 2
    assert wf.execution_generation == 2
