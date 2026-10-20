"""
COMPASS Pydantic Data Models and State Machine Definitions
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskState(str, Enum):
    # Phase 6 Authoritative 20 States
    IDLE = "IDLE"
    UNDERSTANDING = "UNDERSTANDING"
    DECOMPOSING = "DECOMPOSING"
    PERCEIVING = "PERCEIVING"
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    SAFETY_CHECK = "SAFETY_CHECK"
    READY_TO_ACT = "READY_TO_ACT"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    ADAPTING = "ADAPTING"
    STEP_COMPLETED = "STEP_COMPLETED"
    TASK_COMPLETED = "TASK_COMPLETED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"

    # Phase 7 Multimodal Perception States
    MULTIMODAL_PERCEIVING = "MULTIMODAL_PERCEIVING"
    FUSING_EVIDENCE = "FUSING_EVIDENCE"
    TARGET_CONFLICT = "TARGET_CONFLICT"

    # Phase 8 Autonomous Workflow States
    WORKFLOW_PLANNING = "WORKFLOW_PLANNING"
    WORKFLOW_VALIDATING = "WORKFLOW_VALIDATING"
    WORKFLOW_RUNNING = "WORKFLOW_RUNNING"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RECOVERING = "WORKFLOW_RECOVERING"
    WORKFLOW_REPLANNING = "WORKFLOW_REPLANNING"

    # Backward-compatible aliases for Phase 1-5
    CREATED = "CREATED"
    STARTING = "STARTING"
    OBSERVING = "OBSERVING"
    DECIDING = "DECIDING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    REPLANNING = "REPLANNING"
    GUIDING = "GUIDING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"


TERMINAL_STATES = {
    TaskState.TASK_COMPLETED,
    TaskState.COMPLETED,
    TaskState.FAILED,
    TaskState.STOPPED,
    TaskState.CANCELLED,
    TaskState.BLOCKED,
    TaskState.UNVERIFIED,
    TaskState.AI_UNAVAILABLE,
    TaskState.SAFETY_BLOCKED,
}

# Strict, validated state transition rules for COMPASS
VALID_TRANSITIONS: dict[TaskState, list[TaskState]] = {
    TaskState.CREATED: [
        TaskState.STARTING,
        TaskState.IDLE,
        TaskState.PLANNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.IDLE: [
        TaskState.STARTING,
        TaskState.UNDERSTANDING,
        TaskState.DECOMPOSING,
        TaskState.WORKFLOW_PLANNING,
        TaskState.WORKFLOW_VALIDATING,
        TaskState.WORKFLOW_RUNNING,
    ],
    TaskState.STARTING: [
        TaskState.UNDERSTANDING,
        TaskState.DECOMPOSING,
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.WORKFLOW_PLANNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.UNDERSTANDING: [
        TaskState.DECOMPOSING,
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.GUIDING,
        TaskState.WAITING_FOR_USER,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.DECOMPOSING: [
        TaskState.PLANNING,
        TaskState.VALIDATING,
        TaskState.PERCEIVING,
        TaskState.OBSERVING,
        TaskState.WORKFLOW_VALIDATING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.PLANNING: [
        TaskState.VALIDATING,
        TaskState.DECIDING,
        TaskState.SAFETY_CHECK,
        TaskState.READY_TO_ACT,
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.UNDERSTANDING,
        TaskState.DECOMPOSING,
        TaskState.REPLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.WAITING_FOR_USER,
        TaskState.VERIFYING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.OBSERVING: [
        TaskState.DECIDING,
        TaskState.PLANNING,
        TaskState.SAFETY_CHECK,
        TaskState.VALIDATING,
        TaskState.VERIFYING,
        TaskState.COMPLETED,
        TaskState.TASK_COMPLETED,
        TaskState.WAITING_FOR_USER,
        TaskState.WAITING_CONFIRMATION,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.MULTIMODAL_PERCEIVING,
    ],
    TaskState.PERCEIVING: [
        TaskState.DECIDING,
        TaskState.PLANNING,
        TaskState.SAFETY_CHECK,
        TaskState.VALIDATING,
        TaskState.VERIFYING,
        TaskState.COMPLETED,
        TaskState.TASK_COMPLETED,
        TaskState.WAITING_FOR_USER,
        TaskState.WAITING_CONFIRMATION,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.MULTIMODAL_PERCEIVING,
        TaskState.FUSING_EVIDENCE,
        TaskState.TARGET_CONFLICT,
    ],
    TaskState.MULTIMODAL_PERCEIVING: [
        TaskState.FUSING_EVIDENCE,
        TaskState.TARGET_CONFLICT,
        TaskState.PERCEIVING,
        TaskState.SAFETY_CHECK,
        TaskState.VALIDATING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.FUSING_EVIDENCE: [
        TaskState.TARGET_CONFLICT,
        TaskState.SAFETY_CHECK,
        TaskState.READY_TO_ACT,
        TaskState.VALIDATING,
        TaskState.PERCEIVING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    ],
    TaskState.TARGET_CONFLICT: [
        TaskState.RECOVERING,
        TaskState.REPLANNING,
        TaskState.PERCEIVING,
        TaskState.MULTIMODAL_PERCEIVING,
        TaskState.SAFETY_BLOCKED,
        TaskState.BLOCKED,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.DECIDING: [
        TaskState.WAITING_CONFIRMATION,
        TaskState.SAFETY_CHECK,
        TaskState.VALIDATING,
        TaskState.READY_TO_ACT,
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.SAFETY_BLOCKED,
    ],
    TaskState.SAFETY_CHECK: [
        TaskState.READY_TO_ACT,
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.WAITING_CONFIRMATION,
        TaskState.VALIDATING,
        TaskState.SAFETY_BLOCKED,
        TaskState.BLOCKED,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.READY_TO_ACT: [
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.SAFETY_CHECK,
        TaskState.VALIDATING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.SAFETY_BLOCKED,
    ],
    TaskState.WAITING_CONFIRMATION: [
        TaskState.VALIDATING,
        TaskState.SAFETY_CHECK,
        TaskState.READY_TO_ACT,
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.DECIDING,
        TaskState.RECOVERING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.SAFETY_BLOCKED,
    ],
    TaskState.VALIDATING: [
        TaskState.PERCEIVING,
        TaskState.MULTIMODAL_PERCEIVING,
        TaskState.OBSERVING,
        TaskState.SAFETY_CHECK,
        TaskState.READY_TO_ACT,
        TaskState.EXECUTING,
        TaskState.ACTING,
        TaskState.REPLANNING,
        TaskState.ADAPTING,
        TaskState.RECOVERING,
        TaskState.WAITING_FOR_USER,
        TaskState.WAITING_CONFIRMATION,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.SAFETY_BLOCKED,
    ],
    TaskState.EXECUTING: [
        TaskState.VERIFYING,
        TaskState.STEP_COMPLETED,
        TaskState.WAITING_CONFIRMATION,
        TaskState.WAITING_FOR_USER,
        TaskState.RECOVERING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.SAFETY_BLOCKED,
    ],
    TaskState.ACTING: [
        TaskState.VERIFYING,
        TaskState.STEP_COMPLETED,
        TaskState.WAITING_CONFIRMATION,
        TaskState.WAITING_FOR_USER,
        TaskState.RECOVERING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.SAFETY_BLOCKED,
    ],
    TaskState.VERIFYING: [
        TaskState.STEP_COMPLETED,
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.DECIDING,
        TaskState.EXECUTING,
        TaskState.ACTING,
        TaskState.GUIDING,
        TaskState.REPLANNING,
        TaskState.ADAPTING,
        TaskState.RECOVERING,
        TaskState.WAITING_FOR_USER,
        TaskState.COMPLETED,
        TaskState.TASK_COMPLETED,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.UNVERIFIED,
    ],
    TaskState.STEP_COMPLETED: [
        TaskState.DECOMPOSING,
        TaskState.PERCEIVING,
        TaskState.MULTIMODAL_PERCEIVING,
        TaskState.OBSERVING,
        TaskState.PLANNING,
        TaskState.SAFETY_CHECK,
        TaskState.VALIDATING,
        TaskState.READY_TO_ACT,
        TaskState.ACTING,
        TaskState.EXECUTING,
        TaskState.VERIFYING,
        TaskState.COMPLETED,
        TaskState.TASK_COMPLETED,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.REPLANNING: [
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.DECIDING,
        TaskState.WAITING_FOR_USER,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.ADAPTING: [
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.DECOMPOSING,
        TaskState.RECOVERING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
        TaskState.AI_UNAVAILABLE,
    ],
    TaskState.RECOVERING: [
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.MULTIMODAL_PERCEIVING,
        TaskState.PLANNING,
        TaskState.DECIDING,
        TaskState.REPLANNING,
        TaskState.ADAPTING,
        TaskState.WAITING_FOR_USER,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    ],
    TaskState.GUIDING: [
        TaskState.WAITING_FOR_USER,
        TaskState.VERIFYING,
        TaskState.COMPLETED,
        TaskState.TASK_COMPLETED,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.WAITING_FOR_USER: [
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.DECIDING,
        TaskState.VALIDATING,
        TaskState.EXECUTING,
        TaskState.ACTING,
        TaskState.VERIFYING,
        TaskState.GUIDING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.WORKFLOW_PLANNING: [
        TaskState.WORKFLOW_VALIDATING,
        TaskState.WORKFLOW_RUNNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.WORKFLOW_VALIDATING: [
        TaskState.WORKFLOW_RUNNING,
        TaskState.WORKFLOW_PLANNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.WORKFLOW_RUNNING: [
        TaskState.WORKFLOW_PAUSED,
        TaskState.WORKFLOW_RECOVERING,
        TaskState.WORKFLOW_REPLANNING,
        TaskState.ACTING,
        TaskState.VERIFYING,
        TaskState.STEP_COMPLETED,
        TaskState.TASK_COMPLETED,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    ],
    TaskState.WORKFLOW_PAUSED: [
        TaskState.WORKFLOW_RUNNING,
        TaskState.STOPPED,
        TaskState.CANCELLED,
        TaskState.FAILED,
    ],
    TaskState.WORKFLOW_RECOVERING: [
        TaskState.WORKFLOW_RUNNING,
        TaskState.WORKFLOW_REPLANNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.WORKFLOW_REPLANNING: [
        TaskState.WORKFLOW_RUNNING,
        TaskState.WORKFLOW_VALIDATING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.TASK_COMPLETED: [],  # Terminal state
    TaskState.COMPLETED: [],  # Terminal state
    TaskState.FAILED: [TaskState.STARTING, TaskState.IDLE],  # Can retry
    TaskState.STOPPED: [TaskState.STARTING, TaskState.IDLE],  # Can restart
    TaskState.CANCELLED: [TaskState.STARTING, TaskState.IDLE],  # Can restart
    TaskState.BLOCKED: [
        TaskState.STARTING,
        TaskState.IDLE,
        TaskState.RECOVERING,
        TaskState.PLANNING,
        TaskState.OBSERVING,
        TaskState.PERCEIVING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.UNVERIFIED: [
        TaskState.STARTING,
        TaskState.IDLE,
        TaskState.RECOVERING,
        TaskState.PLANNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.AI_UNAVAILABLE: [
        TaskState.STARTING,
        TaskState.IDLE,
        TaskState.PLANNING,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
    TaskState.SAFETY_BLOCKED: [
        TaskState.STARTING,
        TaskState.IDLE,
        TaskState.FAILED,
        TaskState.STOPPED,
        TaskState.CANCELLED,
    ],
}


def is_terminal_state(state: TaskState) -> bool:
    """Check if state is a terminal state."""
    return state in TERMINAL_STATES


def validate_state_transition(current: TaskState, target: TaskState) -> bool:
    """Strictly validate whether transition from current to target state is permissible."""
    # STOP / CANCELLED is universally legal from any non-terminal state
    if target in [TaskState.STOPPED, TaskState.CANCELLED] and not is_terminal_state(
        current
    ):
        return True
    return target in VALID_TRANSITIONS.get(current, [])


class TaskCreate(BaseModel):
    goal: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="Natural language goal provided by the user",
    )
    metadata: dict[str, Any] | None = Field(default_factory=dict)

    @field_validator("goal")
    @classmethod
    def validate_non_empty_goal(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task goal cannot be empty or whitespace only")
        return v.strip()


class TaskTransition(BaseModel):
    new_state: TaskState
    reason: str | None = Field(default="", max_length=500)


class TaskEventResponse(BaseModel):
    id: int
    task_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: float


class TaskResponse(BaseModel):
    id: str
    goal: str
    state: TaskState
    created_at: float
    updated_at: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskDetailResponse(TaskResponse):
    events: list[TaskEventResponse] = Field(default_factory=list)


class SubsystemStatus(BaseModel):
    status: str
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str  # "healthy" or "degraded" or "unhealthy"
    app: str = "COMPASS"
    version: str
    uptime_seconds: float
    timestamp: float
    database: dict[str, Any]
    system: dict[str, Any]


class SystemInfoResponse(BaseModel):
    os: str
    os_version: str
    python_version: str
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    process_pid: int
    uptime_seconds: float


class ShutdownResponse(BaseModel):
    status: str
    message: str


class ActiveWindowResponse(BaseModel):
    app_name: str = "Desktop Workspace"
    window_title: str = "Active Workspace"
    process_id: int = 0
    hwnd: int = 0
    status: str = "active"


# Phase 9 Reliability Models
class IncidentSeverity(str, Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"
    CRITICAL_INTEGRITY_VIOLATION = "CRITICAL_INTEGRITY_VIOLATION"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    REPAIRING = "REPAIRING"
    RESOLVED = "RESOLVED"
    UNRESOLVABLE = "UNRESOLVABLE"


class IncidentModel(BaseModel):
    incident_id: str
    workflow_id: str | None = None
    node_id: str | None = None
    severity: IncidentSeverity
    status: IncidentStatus
    description: str
    created_at: float
    updated_at: float
    metadata: dict[str, Any] = Field(default_factory=dict)
