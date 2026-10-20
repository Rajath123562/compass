"""
COMPASS Phase 3 Planner Data Models
Strongly typed Pydantic models for structured planning, schema validation, and verification.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from backend.app.models import (  # noqa: F401
    TaskState,
    is_terminal_state,
    validate_state_transition,
)


class ConfidenceLevel(str, Enum):
    """Structured confidence scale with well-defined operational semantics."""

    HIGH = "HIGH"  # >= 0.8: High certainty, proceed according to safety rules
    MEDIUM = "MEDIUM"  # 0.5 - 0.79: Reasonable certainty, requires strict verification
    LOW = "LOW"  # < 0.5: Low certainty, requires user confirmation or re-analysis
    UNKNOWN = "UNKNOWN"  # Insufficient evidence or conflicting signals

    @classmethod
    def from_score(cls, score: float) -> ConfidenceLevel:
        if score >= 0.8:
            return cls.HIGH
        elif score >= 0.5:
            return cls.MEDIUM
        elif score > 0.0:
            return cls.LOW
        return cls.UNKNOWN


class RiskLevel(str, Enum):
    """Contextual risk level for planned actions."""

    LOW = "LOW"  # Non-destructive (observe, highlight, scroll, harmless menu open)
    MEDIUM = (
        "MEDIUM"  # Modifying UI state or benign input (typing, non-critical clicks)
    )
    HIGH = "HIGH"  # Destructive, irrecoverable, external side effect, or data loss potential
    CONSEQUENTIAL = (
        "CONSEQUENTIAL"  # Irreversible operations: delete, buy, submit, send, publish
    )
    BLOCKED = (
        "BLOCKED"  # Forbidden or hazardous action requiring explicit human unblock
    )


class GuidanceMode(str, Enum):
    """Operational guidance mode governing autonomous execution boundaries."""

    GUIDE = "GUIDE"  # Visual guidance only, no action executed
    ASSIST = "ASSIST"  # Low-risk auto-executed; medium/high ask confirmation
    CONFIRM = "CONFIRM"  # All computer actions require user approval
    AUTONOMOUS = "AUTONOMOUS"  # Low and medium executed; HIGH unconditionally asks


class FailureClassification(str, Enum):
    """
    Comprehensive Failure Classifications per Phase 5 Specification (§9) + Phase 6 Multi-Step Extensions.
    """

    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TARGET_CHANGED = "TARGET_CHANGED"
    TARGET_DISABLED = "TARGET_DISABLED"
    WRONG_WINDOW = "WRONG_WINDOW"
    PERCEPTION_FAILURE = "PERCEPTION_FAILURE"
    UIA_FAILURE = "UIA_FAILURE"
    SCREEN_CAPTURE_FAILURE = "SCREEN_CAPTURE_FAILURE"
    ACTION_FAILURE = "ACTION_FAILURE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    PLANNER_FAILURE = "PLANNER_FAILURE"
    INVALID_PLAN = "INVALID_PLAN"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    APPLICATION_NOT_READY = "APPLICATION_NOT_READY"
    APPLICATION_CRASHED = "APPLICATION_CRASHED"
    USER_CANCELLED = "USER_CANCELLED"
    SAFETY_REJECTION = "SAFETY_REJECTION"
    RETRY_LIMIT_REACHED = "RETRY_LIMIT_REACHED"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"
    BLOCKED = "BLOCKED"

    # Phase 6 Multi-Step Extensions
    DEPENDENCY_UNMET = "DEPENDENCY_UNMET"
    GOAL_VERIFICATION_FAILED = "GOAL_VERIFICATION_FAILED"
    LOOP_DETECTED = "LOOP_DETECTED"
    REPLAN_EXHAUSTED = "REPLAN_EXHAUSTED"
    CHECKPOINT_INVALID = "CHECKPOINT_INVALID"
    STEP_TIMEOUT = "STEP_TIMEOUT"

    # Phase 7 Multimodal Perception Extensions
    CAPTURE_FAILED = "CAPTURE_FAILED"
    OCR_FAILED = "OCR_FAILED"
    OCR_TIMEOUT = "OCR_TIMEOUT"
    VISION_FAILED = "VISION_FAILED"
    VISION_TIMEOUT = "VISION_TIMEOUT"
    INVALID_VISUAL_OUTPUT = "INVALID_VISUAL_OUTPUT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    TARGET_AMBIGUOUS = "TARGET_AMBIGUOUS"
    TARGET_MOVED = "TARGET_MOVED"
    DPI_MISMATCH = "DPI_MISMATCH"
    MONITOR_CHANGED = "MONITOR_CHANGED"
    WINDOW_CHANGED = "WINDOW_CHANGED"
    APPLICATION_CHANGED = "APPLICATION_CHANGED"
    PERCEPTION_RESOURCE_EXHAUSTED = "PERCEPTION_RESOURCE_EXHAUSTED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    SCREENSHOT_INVALID = "SCREENSHOT_INVALID"
    CHECKPOINT_EVIDENCE_INVALID = "CHECKPOINT_EVIDENCE_INVALID"

    # Phase 8 Autonomous Workflow Extensions
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    WORKFLOW_TIMEOUT = "WORKFLOW_TIMEOUT"
    NODE_TIMEOUT = "NODE_TIMEOUT"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    DEADLOCK_DETECTED = "DEADLOCK_DETECTED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    CHECKPOINT_CORRUPTED = "CHECKPOINT_CORRUPTED"
    WORKFLOW_INVALID = "WORKFLOW_INVALID"

    # Backward-compatible aliases for Phase 4 enums
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    ACTION_REJECTED = "ACTION_REJECTED"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    APPLICATION_CLOSED = "APPLICATION_CLOSED"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"


# Maintain FailureState as a fully compatible alias with all categories + legacy names
FailureState = FailureClassification


class RecoveryCause(str, Enum):
    """Internal causes triggering recovery and adaptive replanning."""

    TARGET_MOVED = "TARGET_MOVED"
    TARGET_DISAPPEARED = "TARGET_DISAPPEARED"
    APPLICATION_CHANGED = "APPLICATION_CHANGED"
    USER_INTERVENTION = "USER_INTERVENTION"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    ACTION_FAILED = "ACTION_FAILED"
    TIMEOUT = "TIMEOUT"


class PlannerActionType(str, Enum):
    """
    Strict action allowlist for the AI planner and Decision Engine.
    Arbitrary system or shell commands are forbidden.
    """

    FOCUS = "focus"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    SCROLL = "scroll"
    TYPE = "type"
    KEY = "key"
    KEY_PRESS = "key_press"
    KEY_COMBINATION = "key_combination"
    WAIT = "wait"
    HIGHLIGHT = "highlight"
    OBSERVE = "observe"
    ASK_USER = "ask_user"
    STOP = "stop"
    REPLAN = "replan"
    VERIFY = "verify"
    LAUNCH_APP = "launch_app"
    OPEN_URL = "open_url"


class TargetReference(BaseModel):
    """UIA-grounded metadata for identifying an element without relying on raw coordinates."""

    hwnd: int | None = Field(default=None, description="Window handle")
    process_id: int | None = Field(default=None, description="PID of application")
    automation_id: str | None = Field(default=None, description="UIA AutomationId")
    control_type: str | None = Field(
        default=None, description="UIA ControlType (e.g. Button, Edit)"
    )
    name: str | None = Field(default=None, description="Accessible element name")
    runtime_id: str | None = Field(default=None, description="UIA runtime ID")
    bounding_rect: dict[str, int] | None = Field(
        default=None, description="Last known bounds"
    )
    window_title: str | None = Field(
        default=None, description="Title of parent window"
    )


class VerificationCondition(BaseModel):
    """Condition to evaluate after action dispatch to verify expected state transition."""

    condition_type: str = Field(
        ...,
        description="Type: text_equals, focused, element_exists, element_disappeared, window_exists, window_title_contains",
    )
    target: TargetReference | None = Field(
        default=None, description="Target element to check"
    )
    expected_value: str | None = Field(
        default=None, description="Expected value/text or state"
    )
    timeout_ms: float = Field(
        default=3000.0, ge=100.0, le=15000.0, description="Verification timeout in ms"
    )


class PlannedAction(BaseModel):
    """Single discrete step within a TaskPlan."""

    action_type: PlannerActionType
    target_reference: TargetReference | None = Field(
        default=None, description="Target UI element"
    )
    target_description: str = Field(
        ..., description="Concise description of the target"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Action parameters (bounded)"
    )
    expected_result: str = Field(
        ..., description="Expected outcome of executing this action"
    )
    verification_condition: VerificationCondition | None = Field(
        default=None, description="Verification rule"
    )
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH)
    safety_class: str = Field(
        default="normal", description="normal, consequential, restricted"
    )

    @model_validator(mode="after")
    def validate_action_parameters(self) -> PlannedAction:
        """Validate parameters according to action type."""
        atype = self.action_type
        params = self.parameters

        if atype == PlannerActionType.TYPE:
            if "text" not in params:
                raise ValueError("Type action requires 'text' parameter.")
            text = str(params["text"])
            if len(text) > 10000:
                raise ValueError(
                    "Text length exceeds maximum allowed limit (10000 chars)."
                )

        elif atype in [PlannerActionType.KEY, PlannerActionType.KEY_PRESS]:
            if "key" not in params:
                raise ValueError("Key action requires 'key' parameter.")
            key_name = str(params["key"]).lower()
            from automation.models import VK_CODES

            if key_name not in VK_CODES:
                raise ValueError(
                    f"Key '{key_name}' is not an allowlisted virtual key code."
                )

        elif atype == PlannerActionType.KEY_COMBINATION:
            if "combination" not in params and "keys" not in params:
                raise ValueError(
                    "Key combination action requires 'combination' or 'keys' parameter."
                )

        elif atype == PlannerActionType.WAIT:
            duration = params.get("duration_ms", 500)
            if (
                not isinstance(duration, (int, float))
                or duration < 0
                or duration > 10000
            ):
                raise ValueError("Wait duration must be between 0 and 10000 ms.")

        elif atype in [
            PlannerActionType.CLICK,
            PlannerActionType.DOUBLE_CLICK,
            PlannerActionType.RIGHT_CLICK,
            PlannerActionType.FOCUS,
            PlannerActionType.HIGHLIGHT,
            PlannerActionType.MOVE,
        ]:
            if not self.target_reference and not self.target_description:
                raise ValueError(
                    f"{atype.value} action must specify target_reference or target_description."
                )

        return self


class TaskPlan(BaseModel):
    """Complete, structured action plan generated by the AI Decision Engine."""

    task_id: str
    goal: str
    steps: list[PlannedAction] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list)
    completion_conditions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH)
    plan_version: int = Field(default=1)
    reasoning_summary: str = Field(
        default="", description="High-level machine-useful rationale summary"
    )


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"
    UNVERIFIED = "UNVERIFIED"


class EvidenceSource(str, Enum):
    UIA = "UIA"
    OCR = "OCR"
    SCREEN_CAPTURE = "SCREEN_CAPTURE"
    WINDOW_STATE = "WINDOW_STATE"
    FILESYSTEM = "FILESYSTEM"
    USER_INPUT = "USER_INPUT"
    VISUAL_MODEL = "VISUAL_MODEL"
    TEMPORAL_COMPARISON = "TEMPORAL_COMPARISON"
    MULTIMODAL_FUSION = "MULTIMODAL_FUSION"


class VerificationResult(BaseModel):
    """Evidence and outcome of post-action verification."""

    status: VerificationStatus
    details: str
    observed_state: dict[str, Any] | None = None
    expected_state: dict[str, Any] | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    evidence_source: EvidenceSource | None = Field(default=EvidenceSource.UIA)
    verification_timestamp: float = Field(default_factory=time.time)
    observation_id: str | None = None
    timestamp: float = Field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "details": self.details,
            "observed_state": self.observed_state,
            "expected_state": self.expected_state,
            "evidence": self.evidence,
            "evidence_source": self.evidence_source.value
            if self.evidence_source
            else None,
            "verification_timestamp": self.verification_timestamp or self.timestamp,
            "observation_id": self.observation_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


class Decision(BaseModel):
    """
    Strict machine-readable decision schema formulated by the Structured Decision Engine.
    Represents a validated single step before execution.
    """

    decision_id: str = Field(..., description="Unique decision ID, e.g. dec_<hex>")
    task_id: str = Field(..., description="Parent task ID")
    observation_id: str = Field(
        default="", description="ID/hash of UI observation this is based upon"
    )
    timestamp: float = Field(default_factory=time.time)
    action: PlannerActionType
    target: TargetReference | None = Field(default=None)
    target_description: str = Field(default="")
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_signals: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    risk_reasons: list[str] = Field(default_factory=list)
    requires_confirmation: bool = Field(default=False)
    human_explanation: str = Field(
        ..., description="Concise, clear explanation for the user"
    )
    expected_result: str = Field(default="")
    verification_strategy: dict[str, Any] | None = Field(default=None)
    recovery_strategy: dict[str, Any] | None = Field(default=None)
    is_repeatable: bool = Field(
        default=True,
        description="False if repeat execution has destructive/side-effect consequences",
    )


class TimelineEntry(BaseModel):
    """
    Rich observability entry recorded for each step in a task's lifecycle.
    Never exposes internal reasoning, private model prompts, or API credentials.
    """

    task_id: str
    decision_id: str
    observation_id: str
    timestamp: float = Field(default_factory=time.time)
    action: str
    target: str
    confidence: str
    risk: str
    approval_state: str  # NOT_REQUIRED, WAITING, GRANTED, REJECTED, INVALIDATED
    validation_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    recovery_action: str | None = None
    human_explanation: str = ""


class StepStatus(str, Enum):
    """Execution status of an individual task step in a multi-step plan."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TaskStep(BaseModel):
    """Structured step representation within a multi-step task decomposition."""

    step_id: str = Field(..., description="Unique step ID within plan, e.g. step_1")
    goal: str = Field(..., description="Objective of this specific step")
    preconditions: list[str] = Field(
        default_factory=list, description="Preconditions required before execution"
    )
    target: TargetReference | None = Field(
        default=None, description="Target element metadata"
    )
    target_description: str = Field(
        default="", description="Descriptive label for target"
    )
    candidate_actions: list[PlannedAction] = Field(
        default_factory=list, description="Planned actions for this step"
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    repeatability: bool = Field(
        default=True, description="False if action is consequential or non-repeatable"
    )
    expected_state_change: str = Field(
        default="", description="Expected delta in UI/OS state"
    )
    verification_strategy: str = Field(
        default="UIA_PATTERN",
        description="Verification method: UIA_PATTERN, TEXT_EQUALS, WINDOW_STATE, FILESYSTEM",
    )
    recovery_strategy: str = Field(
        default="REPERCEIVE_DRIFT",
        description="Recovery protocol: REPERCEIVE_DRIFT, RETRY_ONCE, ALTERNATE_INVOKE, REPLAN, HALT",
    )
    completion_condition: dict[str, Any] = Field(
        default_factory=dict, description="Machine-evaluable post-condition"
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Step IDs that must complete before this step can execute",
    )
    status: StepStatus = Field(default=StepStatus.PENDING)
    error: str | None = None
    execution_time_s: float = 0.0


class DecomposedPlan(BaseModel):
    """Multi-step plan produced by TaskDecomposer with explicit step dependencies."""

    task_id: str
    goal: str
    steps: list[TaskStep] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(
        default_factory=dict, description="Step ID to list of prerequisite step IDs"
    )
    created_at: float = Field(default_factory=time.time)
    version: int = Field(default=1)
    plan_hash: str = Field(default="")
    estimated_duration_s: float = 0.0
    max_execution_time_s: float = 180.0
