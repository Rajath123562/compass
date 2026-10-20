"""
Exhaustive State Machine Tests (Phase 4, Addendum §28, Directive §23).
Tests all valid transitions, invalid jumps, terminal states, cancellation, and restart paths.
"""

import pytest
from fastapi import HTTPException

from backend.app.models import VALID_TRANSITIONS, TaskState
from backend.app.services.task_service import task_service


def test_state_machine_valid_closed_loop_path():
    """Verify standard happy-path closed-loop progression."""
    task = task_service.create_task("State Machine Closed-Loop Test")
    tid = task["id"]

    assert task["state"] == TaskState.STARTING

    # STARTING -> UNDERSTANDING
    t = task_service.transition_state(tid, TaskState.UNDERSTANDING)
    assert t["state"] == TaskState.UNDERSTANDING

    # UNDERSTANDING -> OBSERVING
    t = task_service.transition_state(tid, TaskState.OBSERVING)
    assert t["state"] == TaskState.OBSERVING

    # OBSERVING -> PLANNING
    t = task_service.transition_state(tid, TaskState.PLANNING)
    assert t["state"] == TaskState.PLANNING

    # PLANNING -> DECIDING
    t = task_service.transition_state(tid, TaskState.DECIDING)
    assert t["state"] == TaskState.DECIDING

    # DECIDING -> WAITING_CONFIRMATION
    t = task_service.transition_state(tid, TaskState.WAITING_CONFIRMATION)
    assert t["state"] == TaskState.WAITING_CONFIRMATION

    # WAITING_CONFIRMATION -> VALIDATING
    t = task_service.transition_state(tid, TaskState.VALIDATING)
    assert t["state"] == TaskState.VALIDATING

    # VALIDATING -> ACTING
    t = task_service.transition_state(tid, TaskState.ACTING)
    assert t["state"] == TaskState.ACTING

    # ACTING -> VERIFYING
    t = task_service.transition_state(tid, TaskState.VERIFYING)
    assert t["state"] == TaskState.VERIFYING

    # VERIFYING -> COMPLETED
    t = task_service.transition_state(tid, TaskState.COMPLETED)
    assert t["state"] == TaskState.COMPLETED


def test_state_machine_invalid_jumps_rejected():
    """Directive §23: Verify that illegal state jumps are strictly rejected."""
    task = task_service.create_task("Invalid Jump Test")
    tid = task["id"]

    # STARTING -> COMPLETED (illegal skip)
    with pytest.raises(HTTPException) as exc:
        task_service.transition_state(tid, TaskState.COMPLETED)
    assert exc.value.status_code == 400
    assert "Invalid state transition" in exc.value.detail

    # STARTING -> ACTING (illegal skip)
    with pytest.raises(HTTPException) as exc:
        task_service.transition_state(tid, TaskState.ACTING)
    assert exc.value.status_code == 400

    # STARTING -> RECOVERING (illegal)
    with pytest.raises(HTTPException) as exc:
        task_service.transition_state(tid, TaskState.RECOVERING)
    assert exc.value.status_code == 400


def test_state_machine_terminal_state_completed_cannot_transition():
    task = task_service.create_task("Terminal State Test")
    tid = task["id"]
    task_service.transition_state(tid, TaskState.UNDERSTANDING)
    task_service.transition_state(tid, TaskState.OBSERVING)
    task_service.transition_state(tid, TaskState.VERIFYING)
    task_service.transition_state(tid, TaskState.COMPLETED)

    # COMPLETED is terminal: no transitions allowed
    with pytest.raises(HTTPException) as exc:
        task_service.transition_state(tid, TaskState.PLANNING)
    assert exc.value.status_code == 400


def test_state_machine_cancellation_and_restart():
    task = task_service.create_task("Cancel Test")
    tid = task["id"]
    task_service.transition_state(tid, TaskState.UNDERSTANDING)
    task_service.transition_state(tid, TaskState.CANCELLED)

    # CANCELLED -> STARTING (restart allowed)
    t = task_service.transition_state(tid, TaskState.STARTING)
    assert t["state"] == TaskState.STARTING


def test_state_machine_recovery_path():
    task = task_service.create_task("Recovery State Test")
    tid = task["id"]
    task_service.transition_state(tid, TaskState.UNDERSTANDING)
    task_service.transition_state(tid, TaskState.OBSERVING)
    task_service.transition_state(tid, TaskState.DECIDING)
    task_service.transition_state(tid, TaskState.VALIDATING)
    task_service.transition_state(tid, TaskState.ACTING)
    task_service.transition_state(tid, TaskState.VERIFYING)

    # VERIFYING -> RECOVERING
    t = task_service.transition_state(tid, TaskState.RECOVERING)
    assert t["state"] == TaskState.RECOVERING

    # RECOVERING -> OBSERVING
    t = task_service.transition_state(tid, TaskState.OBSERVING)
    assert t["state"] == TaskState.OBSERVING


def test_all_twenty_states_exist_in_enum_and_valid_transitions():
    """Verify that all TaskState values exist (including Phase 5, Phase 6, Phase 7, and Phase 8 extensions) and every state is defined in VALID_TRANSITIONS."""
    all_states = list(TaskState)
    assert len(all_states) in [24, 30, 33, 39, 40], (
        f"Expected 24, 30, 33, 39, or 40 TaskState values, found {len(all_states)}"
    )

    expected_states = {
        "CREATED",
        "IDLE",
        "STARTING",
        "UNDERSTANDING",
        "PLANNING",
        "OBSERVING",
        "DECIDING",
        "WAITING_CONFIRMATION",
        "VALIDATING",
        "ACTING",
        "EXECUTING",
        "VERIFYING",
        "RECOVERING",
        "REPLANNING",
        "GUIDING",
        "WAITING_FOR_USER",
        "COMPLETED",
        "FAILED",
        "STOPPED",
        "CANCELLED",
        "BLOCKED",
        "PERCEIVING",
        "UNVERIFIED",
        "AI_UNAVAILABLE",
        "SAFETY_BLOCKED",
        "DECOMPOSING",
        "SAFETY_CHECK",
        "READY_TO_ACT",
        "ADAPTING",
        "STEP_COMPLETED",
        "TASK_COMPLETED",
        "MULTIMODAL_PERCEIVING",
        "FUSING_EVIDENCE",
        "TARGET_CONFLICT",
        "WORKFLOW_PLANNING",
        "WORKFLOW_VALIDATING",
        "WORKFLOW_RUNNING",
        "WORKFLOW_PAUSED",
        "WORKFLOW_RECOVERING",
        "WORKFLOW_REPLANNING",
    }
    actual_states = {s.value for s in all_states}
    assert actual_states == expected_states

    for state in all_states:
        assert state in VALID_TRANSITIONS, (
            f"State {state} missing from VALID_TRANSITIONS"
        )


def test_terminal_states_cannot_execute_further_actions():
    """Verify that terminal states (COMPLETED) forbid all forward transitions."""
    task = task_service.create_task("Terminal Completion Guard")
    tid = task["id"]
    task_service.transition_state(tid, TaskState.UNDERSTANDING)
    task_service.transition_state(tid, TaskState.OBSERVING)
    task_service.transition_state(tid, TaskState.VERIFYING)
    task_service.transition_state(tid, TaskState.COMPLETED)

    # All attempts to jump to active states must be rejected
    for target in [
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.PLANNING,
        TaskState.DECIDING,
        TaskState.VALIDATING,
    ]:
        with pytest.raises(HTTPException) as exc:
            task_service.transition_state(tid, target)
        assert exc.value.status_code == 400


def test_no_bypass_of_validation_approval_safety():
    """Verify that no state transition allows bypassing validation, approval, or safety checks."""
    task = task_service.create_task("Bypass Rejection Test")
    tid = task["id"]

    # Direct jump to execution from STARTING must fail
    with pytest.raises(HTTPException):
        task_service.transition_state(tid, TaskState.ACTING)

    with pytest.raises(HTTPException):
        task_service.transition_state(tid, TaskState.EXECUTING)

    # Direct jump to COMPLETED from STARTING must fail
    with pytest.raises(HTTPException):
        task_service.transition_state(tid, TaskState.COMPLETED)


def test_stop_and_cancellation_safe_from_active_states():
    """Verify that STOPPED and CANCELLED transitions succeed from all active operational states."""
    active_states = [
        TaskState.STARTING,
        TaskState.UNDERSTANDING,
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.DECIDING,
        TaskState.WAITING_CONFIRMATION,
        TaskState.VALIDATING,
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.VERIFYING,
        TaskState.RECOVERING,
        TaskState.REPLANNING,
    ]

    for state in active_states:
        allowed_transitions = VALID_TRANSITIONS.get(state, [])
        assert TaskState.STOPPED in allowed_transitions, (
            f"State {state} cannot transition to STOPPED"
        )
        assert TaskState.CANCELLED in allowed_transitions, (
            f"State {state} cannot transition to CANCELLED"
        )


def test_multimodal_perception_state_transitions():
    """Verify Phase 7 Multimodal Perception, Fusion, and Conflict state progression."""
    task = task_service.create_task("Phase 7 State Machine Test")
    tid = task["id"]

    # STARTING -> UNDERSTANDING -> DECOMPOSING -> VALIDATING -> MULTIMODAL_PERCEIVING
    task_service.transition_state(tid, TaskState.UNDERSTANDING)
    task_service.transition_state(tid, TaskState.DECOMPOSING)
    task_service.transition_state(tid, TaskState.VALIDATING)
    t = task_service.transition_state(tid, TaskState.MULTIMODAL_PERCEIVING)
    assert t["state"] == TaskState.MULTIMODAL_PERCEIVING

    # MULTIMODAL_PERCEIVING -> FUSING_EVIDENCE
    t = task_service.transition_state(tid, TaskState.FUSING_EVIDENCE)
    assert t["state"] == TaskState.FUSING_EVIDENCE

    # FUSING_EVIDENCE -> SAFETY_CHECK -> READY_TO_ACT
    t = task_service.transition_state(tid, TaskState.SAFETY_CHECK)
    assert t["state"] == TaskState.SAFETY_CHECK


def test_target_conflict_safety_blocking():
    """Verify TARGET_CONFLICT transitions to SAFETY_BLOCKED or RECOVERING and rejects arbitrary jumps."""
    task = task_service.create_task("Conflict Safety Test")
    tid = task["id"]

    task_service.transition_state(tid, TaskState.UNDERSTANDING)
    task_service.transition_state(tid, TaskState.DECOMPOSING)
    task_service.transition_state(tid, TaskState.VALIDATING)
    task_service.transition_state(tid, TaskState.MULTIMODAL_PERCEIVING)

    # Transition to TARGET_CONFLICT
    t = task_service.transition_state(tid, TaskState.TARGET_CONFLICT)
    assert t["state"] == TaskState.TARGET_CONFLICT

    # Illegal jump to TASK_COMPLETED must fail
    with pytest.raises(HTTPException):
        task_service.transition_state(tid, TaskState.TASK_COMPLETED)

    # Illegal jump to ACTING must fail
    with pytest.raises(HTTPException):
        task_service.transition_state(tid, TaskState.ACTING)

    # Valid transition to SAFETY_BLOCKED
    t = task_service.transition_state(tid, TaskState.SAFETY_BLOCKED)
    assert t["state"] == TaskState.SAFETY_BLOCKED
