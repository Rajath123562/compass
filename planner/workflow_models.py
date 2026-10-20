"""
COMPASS Phase 8 — Autonomous Workflow Data Models
Strongly typed models for workflows, nodes, DAG structure, resource budgets,
retry policies, and execution fencing.

Authoritative state machines for both Workflow and Node lifecycles.
All state transitions are validated through deterministic transition matrices.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Section 2/3: Authoritative Workflow State Machine
# ---------------------------------------------------------------------------


class WorkflowStatus(str, Enum):
    """Authoritative workflow lifecycle states (18 explicit statuses)."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_RESOURCE = "WAITING_RESOURCE"
    WAITING_USER = "WAITING_USER"
    REPLANNING = "REPLANNING"
    RECOVERING = "RECOVERING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"
    STOPPED = "STOPPED"
    TIMED_OUT = "TIMED_OUT"


WORKFLOW_TERMINAL_STATES: set[WorkflowStatus] = {
    WorkflowStatus.COMPLETED,
    WorkflowStatus.FAILED,
    WorkflowStatus.CANCELLED,
    WorkflowStatus.STOPPED,
    WorkflowStatus.TIMED_OUT,
}

# Complete legal transition matrix for workflows (Section 2)
WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.CREATED: {
        WorkflowStatus.VALIDATING,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.VALIDATING: {
        WorkflowStatus.WAITING_APPROVAL,
        WorkflowStatus.READY,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.WAITING_APPROVAL: {
        WorkflowStatus.READY,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.READY: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.RUNNING: {
        WorkflowStatus.PAUSED,
        WorkflowStatus.WAITING_RESOURCE,
        WorkflowStatus.WAITING_USER,
        WorkflowStatus.REPLANNING,
        WorkflowStatus.RECOVERING,
        WorkflowStatus.PARTIALLY_COMPLETED,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.UNKNOWN,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
        WorkflowStatus.TIMED_OUT,
    },
    WorkflowStatus.PAUSED: {
        WorkflowStatus.RUNNING,  # Only through validated RESUME path
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.WAITING_RESOURCE: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
        WorkflowStatus.TIMED_OUT,
    },
    WorkflowStatus.WAITING_USER: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.REPLANNING: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.RECOVERING: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.UNKNOWN,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.PARTIALLY_COMPLETED: {
        WorkflowStatus.RUNNING,  # Resume remaining
        WorkflowStatus.REPLANNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    # Terminal states — no forward transitions except explicit restart
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.FAILED: {WorkflowStatus.RECOVERING},
    WorkflowStatus.BLOCKED: {
        WorkflowStatus.RECOVERING,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.UNKNOWN: {
        WorkflowStatus.RECOVERING,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.CANCELLED: set(),
    WorkflowStatus.STOPPED: set(),
    WorkflowStatus.TIMED_OUT: {WorkflowStatus.RECOVERING, WorkflowStatus.CANCELLED},
}


def validate_workflow_transition(
    current: WorkflowStatus, target: WorkflowStatus
) -> bool:
    """Strictly validate whether a workflow state transition is legal."""
    if current == target:
        return False  # No-op transitions are not valid
    return target in WORKFLOW_TRANSITIONS.get(current, set())


def is_workflow_terminal(status: WorkflowStatus) -> bool:
    return status in WORKFLOW_TERMINAL_STATES


# ---------------------------------------------------------------------------
# Section 3: Authoritative Node State Machine
# ---------------------------------------------------------------------------


class WorkflowNodeStatus(str, Enum):
    """Authoritative node lifecycle states (13 explicit statuses)."""

    PENDING = "PENDING"
    BLOCKED_BY_DEPENDENCY = "BLOCKED_BY_DEPENDENCY"
    READY = "READY"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


NODE_TERMINAL_STATES: set[WorkflowNodeStatus] = {
    WorkflowNodeStatus.COMPLETED,
    WorkflowNodeStatus.FAILED,
    WorkflowNodeStatus.SKIPPED,
    WorkflowNodeStatus.CANCELLED,
    WorkflowNodeStatus.STOPPED,
}

# Complete legal node transition matrix (Section 3)
NODE_TRANSITIONS: dict[WorkflowNodeStatus, set[WorkflowNodeStatus]] = {
    WorkflowNodeStatus.PENDING: {
        WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY,
        WorkflowNodeStatus.READY,
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.SKIPPED,
    },
    WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY: {
        WorkflowNodeStatus.READY,  # Dependency satisfied after recovery/replan
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.SKIPPED,
        WorkflowNodeStatus.STOPPED,
    },
    WorkflowNodeStatus.READY: {
        WorkflowNodeStatus.WAITING_APPROVAL,
        WorkflowNodeStatus.RUNNING,
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.STOPPED,
    },
    WorkflowNodeStatus.WAITING_APPROVAL: {
        WorkflowNodeStatus.RUNNING,  # Approval granted
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.STOPPED,
        WorkflowNodeStatus.FAILED,  # Approval denied
    },
    WorkflowNodeStatus.RUNNING: {
        WorkflowNodeStatus.VERIFYING,
        WorkflowNodeStatus.COMPLETED,
        WorkflowNodeStatus.FAILED,
        WorkflowNodeStatus.UNKNOWN,
        WorkflowNodeStatus.STOPPED,
    },
    WorkflowNodeStatus.VERIFYING: {
        WorkflowNodeStatus.COMPLETED,
        WorkflowNodeStatus.FAILED,
        WorkflowNodeStatus.UNKNOWN,
        WorkflowNodeStatus.STOPPED,
    },
    WorkflowNodeStatus.COMPLETED: set(),  # Terminal
    WorkflowNodeStatus.FAILED: {
        WorkflowNodeStatus.RETRYING,
        WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY,  # Cascade
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.UNKNOWN,
    },
    WorkflowNodeStatus.RETRYING: {
        WorkflowNodeStatus.READY,  # Re-enter ready state
        WorkflowNodeStatus.FAILED,  # Retry exhausted
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.STOPPED,
    },
    WorkflowNodeStatus.SKIPPED: set(),  # Terminal
    WorkflowNodeStatus.CANCELLED: set(),  # Terminal
    WorkflowNodeStatus.STOPPED: set(),  # Terminal
    WorkflowNodeStatus.UNKNOWN: {
        WorkflowNodeStatus.RETRYING,
        WorkflowNodeStatus.FAILED,
        WorkflowNodeStatus.CANCELLED,
        WorkflowNodeStatus.STOPPED,
    },
}


def validate_node_transition(
    current: WorkflowNodeStatus, target: WorkflowNodeStatus
) -> bool:
    """Strictly validate whether a node state transition is legal."""
    if current == target:
        return False
    return target in NODE_TRANSITIONS.get(current, set())


def is_node_terminal(status: WorkflowNodeStatus) -> bool:
    return status in NODE_TERMINAL_STATES


# ---------------------------------------------------------------------------
# Section 19: Retry Policy
# ---------------------------------------------------------------------------


class RetryPolicy(BaseModel):
    """Bounded retry policy with backoff and error classification."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    min_backoff_ms: float = Field(default=500.0, ge=0.0)
    max_backoff_ms: float = Field(default=10000.0, ge=0.0)
    jitter_ms: float = Field(default=200.0, ge=0.0)
    retryable_errors: list[str] = Field(
        default_factory=lambda: [
            "PROVIDER_TIMEOUT",
            "AI_UNAVAILABLE",
            "TARGET_NOT_FOUND",
            "PERCEPTION_FAILURE",
            "TIMEOUT",
        ]
    )
    non_retryable_errors: list[str] = Field(
        default_factory=lambda: [
            "SAFETY_BLOCKED",
            "SAFETY_REJECTION",
            "PERMISSION_DENIED",
            "USER_CANCELLED",
            "CHECKPOINT_CORRUPTED",
        ]
    )

    def is_retryable(self, error: str) -> bool:
        """Evaluate if an error description qualifies for retry."""
        err_upper = (error or "").upper()
        if any(non.upper() in err_upper for non in self.non_retryable_errors):
            return False
        if any(ret.upper() in err_upper for ret in self.retryable_errors):
            return True
        return True

    def get_backoff_seconds(self, attempt: int) -> float:
        """Calculate exponential backoff duration in seconds."""
        backoff_ms = min(
            self.max_backoff_ms, self.min_backoff_ms * (2 ** max(0, attempt - 1))
        )
        return backoff_ms / 1000.0


# ---------------------------------------------------------------------------
# Section 30: Resource Budget
# ---------------------------------------------------------------------------


class ResourceBudget(BaseModel):
    """Per-workflow resource budget with measured enforcement."""

    max_duration_s: float = Field(default=600.0, ge=10.0, le=3600.0)
    max_nodes: int = Field(default=30, ge=1, le=100)
    max_retries: int = Field(default=15, ge=0, le=50)
    max_model_calls: int = Field(default=50, ge=1, le=200)
    max_perception_calls: int = Field(default=100, ge=1, le=500)
    max_memory_mb: float = Field(default=250.0, ge=50.0)
    max_vram_mb: float = Field(default=1000.0, ge=0.0)
    max_concurrent_nodes: int = Field(default=2, ge=1, le=4)


# ---------------------------------------------------------------------------
# Section 7: Workflow Node
# ---------------------------------------------------------------------------


class WorkflowNode(BaseModel):
    """Strongly typed DAG node within an autonomous workflow."""

    node_id: str = Field(default="", description="Unique node ID within workflow")
    workflow_id: str = Field(default="", description="Parent workflow ID")
    description: str = Field(default="", description="Human-readable description")
    goal: str = Field(default="", description="Objective of this node")
    operation: str = Field(default="ui_action", description="Operation type")
    action: Any = Field(
        default_factory=dict, description="Action payload/parameters"
    )
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict, description="Execution result")
    dependencies: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)
    status: WorkflowNodeStatus = Field(default=WorkflowNodeStatus.PENDING)
    priority: int = Field(default=5)
    risk_level: str = Field(default="LOW")
    approval_required: bool = Field(default=False)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout_s: float = Field(default=60.0, ge=5.0, le=600.0)
    resource_requirements: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[Any] = Field(default_factory=list)
    postconditions: list[Any] = Field(default_factory=list)
    verification_policy: str = Field(default="UIA_VERIFY")
    execution_generation: int = Field(default=0)
    generation: int = 0
    required_locks: list[str] = Field(default_factory=list)
    attempt_count: int = Field(default=0)
    checkpoint_reference: str | None = None
    result_reference: str | None = None
    evidence_reference: str | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None

    def __init__(self, **data: Any):
        if "id" in data and "node_id" not in data:
            data["node_id"] = data["id"]
        if "depends_on" in data and "dependencies" not in data:
            data["dependencies"] = data["depends_on"]
        if "state" in data and "status" not in data:
            data["status"] = data["state"]
        if "action" in data and isinstance(data["action"], str):
            if "goal" not in data:
                data["goal"] = data["action"]
            data["action"] = {"type": data["action"]}
        elif "goal" in data and "action" not in data:
            data["action"] = {"type": data["goal"]}
        super().__init__(**data)

    @property
    def id(self) -> str:
        return self.node_id

    @id.setter
    def id(self, val: str) -> None:
        self.node_id = val

    @property
    def depends_on(self) -> list[str]:
        return self.dependencies

    @depends_on.setter
    def depends_on(self, val: list[str]) -> None:
        self.dependencies = val

    @property
    def state(self) -> Any:
        return self.status

    @state.setter
    def state(self, val: Any) -> None:
        self.status = val

    def transition_to(self, target: WorkflowNodeStatus) -> bool:
        """Atomically transition node state through the authoritative state machine."""
        if not validate_node_transition(self.status, target):
            return False
        self.status = target
        if target == WorkflowNodeStatus.RUNNING and self.started_at is None:
            self.started_at = time.time()
        if is_node_terminal(target):
            self.completed_at = time.time()
        return True


class WorkflowState(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    RECOVERING = "RECOVERING"
    REPLANNING = "REPLANNING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    TIMED_OUT = "TIMED_OUT"
    RESOURCE_STARVED = "RESOURCE_STARVED"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"
    UNKNOWN = "UNKNOWN"


class NodeState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    SKIPPED = "SKIPPED"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    RESOURCE_STARVED = "RESOURCE_STARVED"
    RETRYING = "RETRYING"
    ABORTED = "ABORTED"


class WorkflowGraph(BaseModel):
    workflow_id: str
    nodes: dict[str, WorkflowNode] = Field(default_factory=dict)
    state: WorkflowState = WorkflowState.PENDING
    created_at: float = 0.0
    deadline: float = 0.0
    generation: int = 0




# ---------------------------------------------------------------------------
# SSE Event Types (Section 33/29)
# ---------------------------------------------------------------------------


class WorkflowEventType(str, Enum):
    """Authoritative SSE event types for workflow lifecycle."""

    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_VALIDATING = "workflow_validating"
    WORKFLOW_READY = "workflow_ready"
    WORKFLOW_STARTED = "workflow_started"
    NODE_READY = "node_ready"
    NODE_STARTED = "node_started"
    NODE_WAITING_APPROVAL = "node_waiting_approval"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_RETRYING = "node_retrying"
    WORKFLOW_REPLANNING = "workflow_replanning"
    WORKFLOW_RECOVERING = "workflow_recovering"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_WAITING_USER = "workflow_waiting_user"
    WORKFLOW_STOPPED = "workflow_stopped"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_BLOCKED = "workflow_blocked"
    WORKFLOW_UNKNOWN = "workflow_unknown"
    WORKFLOW_TIMED_OUT = "workflow_timed_out"
    CHECKPOINT_CREATED = "checkpoint_created"


# ---------------------------------------------------------------------------
# Section 6: Workflow Model
# ---------------------------------------------------------------------------


def _generate_workflow_id() -> str:
    """Cryptographically strong workflow ID."""
    return f"wf_{uuid.uuid4().hex[:16]}"


def _generate_node_id(workflow_id: str, index: int) -> str:
    """Deterministic node ID scoped to workflow."""
    return f"{workflow_id}_n{index:03d}"


class Workflow(BaseModel):
    """Complete autonomous workflow with DAG, resource budget, and lifecycle state."""

    workflow_id: str = Field(default_factory=_generate_workflow_id)
    task_id: str = Field(default="")
    goal: str = Field(..., description="User goal for this workflow")
    description: str = Field(default="")
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    priority: int = Field(default=5, ge=1, le=10)
    mode: str = Field(default="AUTONOMOUS")
    status: WorkflowStatus = Field(default=WorkflowStatus.CREATED)
    nodes: list[WorkflowNode] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    checkpoint_reference: str | None = None
    resource_budget: ResourceBudget = Field(default_factory=ResourceBudget)
    deadline: float | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    approval_policy: str = Field(default="CONSEQUENTIAL_ONLY")
    execution_generation: int = Field(default=1)
    owner_session: str = Field(default="default")
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: float | None = None
    completed_at: float | None = None

    # Resource accounting (Section 17)
    model_calls_used: int = Field(default=0)
    perception_calls_used: int = Field(default=0)
    retry_count_used: int = Field(default=0)

    def transition_to(self, target: WorkflowStatus) -> bool:
        """Atomically transition workflow state through the authoritative state machine."""
        if not validate_workflow_transition(self.status, target):
            return False
        self.status = target
        self.updated_at = time.time()
        return True

    def increment_generation(self) -> int:
        """Increment execution generation for fencing (Section 24)."""
        self.execution_generation += 1
        self.updated_at = time.time()
        return self.execution_generation

    def get_node(self, node_id: str) -> WorkflowNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_nodes_by_status(self, status: WorkflowNodeStatus) -> list[WorkflowNode]:
        return [n for n in self.nodes if n.status == status]

    def compute_progress(self) -> dict[str, Any]:
        """Compute truthful DAG-based progress (Section 35). No fake percentages."""
        total = len(self.nodes)
        if total == 0:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "running": 0,
                "pending": 0,
                "progress_ratio": 0.0,
            }
        completed = sum(
            1 for n in self.nodes if n.status == WorkflowNodeStatus.COMPLETED
        )
        failed = sum(1 for n in self.nodes if n.status == WorkflowNodeStatus.FAILED)
        running = sum(1 for n in self.nodes if n.status == WorkflowNodeStatus.RUNNING)
        pending = sum(
            1
            for n in self.nodes
            if n.status
            in {
                WorkflowNodeStatus.PENDING,
                WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY,
                WorkflowNodeStatus.READY,
                WorkflowNodeStatus.WAITING_APPROVAL,
            }
        )
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "progress_ratio": round(completed / total, 4) if total > 0 else 0.0,
        }

    def check_resource_budget(self) -> tuple[bool, str]:
        """Check whether workflow is within resource budget (Section 16)."""
        elapsed = time.time() - self.created_at
        if elapsed > self.resource_budget.max_duration_s:
            return (
                False,
                f"Workflow duration {elapsed:.1f}s exceeds budget {self.resource_budget.max_duration_s}s",
            )
        if len(self.nodes) > self.resource_budget.max_nodes:
            return (
                False,
                f"Node count {len(self.nodes)} exceeds budget {self.resource_budget.max_nodes}",
            )
        if self.retry_count_used > self.resource_budget.max_retries:
            return (
                False,
                f"Retry count {self.retry_count_used} exceeds budget {self.resource_budget.max_retries}",
            )
        if self.model_calls_used > self.resource_budget.max_model_calls:
            return (
                False,
                f"Model calls {self.model_calls_used} exceeds budget {self.resource_budget.max_model_calls}",
            )
        if self.perception_calls_used > self.resource_budget.max_perception_calls:
            return (
                False,
                f"Perception calls {self.perception_calls_used} exceeds budget {self.resource_budget.max_perception_calls}",
            )
        return True, "Within budget"
