"""
COMPASS Phase 4 — Human Approval Controller & Anti-Bypass Layer
Enforces operational modes (GUIDE, ASSIST, CONFIRM, AUTONOMOUS).
Guarantees HIGH-risk actions never bypass approval in any mode.
Binds approvals to complete state contexts and invalidates on any drift.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.app.logging_config import logger
from planner.models import Decision, GuidanceMode, PlannerActionType, RiskLevel

APPROVAL_SECRET_KEY = b"COMPASS_HUMAN_APPROVAL_KEY_9921"


def compute_action_approval_digest(
    task_id: str,
    step_id: str,
    action_type: str,
    target: str,
    params: dict[str, Any] | None = None,
    secret_key: bytes = APPROVAL_SECRET_KEY,
) -> str:
    """Compute HMAC-SHA256 signature binding task, step, action, target and parameters."""
    canonical_payload = json.dumps(
        {
            "task_id": str(task_id or ""),
            "step_id": str(step_id or ""),
            "action_type": str(action_type or "").lower().strip(),
            "target": str(target or "").strip(),
            "params": params or {},
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hmac.new(secret_key, canonical_payload, hashlib.sha256).hexdigest()


class ApprovalState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    CONSUMED = "CONSUMED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


class ApprovalRecord(BaseModel):
    approval_id: str
    task_id: str
    decision_id: str
    action: str
    action_parameters: dict[str, Any] = Field(default_factory=dict)
    target_identifier: str
    target_bounds: dict[str, Any] | None = None
    window_hwnd: int | None = None
    application_name: str | None = None
    observation_timestamp: float
    risk_level: RiskLevel
    state: ApprovalState = ApprovalState.PENDING
    approval_token: str | None = None
    created_at: float = Field(default_factory=time.time)
    granted_at: float | None = None
    consumed_at: float | None = None
    expires_at: float
    invalidation_reason: str | None = None
    display_context: dict[str, Any] | None = None


class HumanApprovalController:
    """
    State-bound human approval engine.
    Ensures zero approval bypass across all modes and state drift invalidation.
    """

    def __init__(self, default_mode: GuidanceMode = GuidanceMode.ASSIST):
        self._mode = default_mode
        self._approvals: dict[
            str, ApprovalRecord
        ] = {}  # key: f"{task_id}:{decision_id}"
        self._consumed_ids: set[str] = set()

    def _persist_record(self, record: ApprovalRecord) -> None:
        """Persist approval record to SQLite database if available (§7)."""
        try:
            from backend.app.database import db

            db.save_approval(
                {
                    "approval_id": record.approval_id,
                    "task_id": record.task_id,
                    "decision_id": record.decision_id,
                    "action": record.action,
                    "target_identifier": record.target_identifier,
                    "risk_level": record.risk_level.value
                    if hasattr(record.risk_level, "value")
                    else str(record.risk_level),
                    "state": record.state.value
                    if hasattr(record.state, "value")
                    else str(record.state),
                    "created_at": record.created_at,
                    "granted_at": record.granted_at,
                    "consumed_at": record.consumed_at,
                    "expires_at": record.expires_at,
                    "invalidation_reason": record.invalidation_reason,
                    "payload": {
                        "action_parameters": record.action_parameters,
                        "target_bounds": record.target_bounds,
                        "window_hwnd": record.window_hwnd,
                        "application_name": record.application_name,
                        "observation_timestamp": record.observation_timestamp,
                    },
                }
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Could not persist approval record to DB: {e}")

    @property
    def mode(self) -> GuidanceMode:
        return self._mode

    def set_mode(self, mode: GuidanceMode) -> None:
        logger.info(
            f"HumanApprovalController mode switched from {self._mode.value} to {mode.value}"
        )
        self._mode = mode

    def should_require_approval(self, decision: Decision) -> bool:
        """
        Evaluate whether the decision requires explicit human approval.
        Rule 1: In GUIDE mode, ALL actions require approval / guidance only.
        Rule 2: HIGH-risk actions UNCONDITIONALLY require confirmation across ALL modes.
        Rule 3: In CONFIRM mode, all computer-altering actions require confirmation.
        Rule 4: In ASSIST mode, medium and high risk require confirmation; low proceeds.
        Rule 5: In AUTONOMOUS mode, LOW and MEDIUM proceed; HIGH unconditionally requires confirmation.
        """
        if self._mode == GuidanceMode.GUIDE:
            return True

        if decision.risk_level == RiskLevel.HIGH or decision.requires_confirmation:
            # Absolute requirement per Directive §9 and Addendum §6
            return True

        if self._mode == GuidanceMode.CONFIRM:
            # Non-invasive observe/wait do not interact with computer state
            if decision.action in [PlannerActionType.OBSERVE, PlannerActionType.WAIT]:  # noqa: SIM103
                return False
            return True

        if self._mode == GuidanceMode.ASSIST:
            if decision.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]:  # noqa: SIM103
                return True
            return False

        if self._mode == GuidanceMode.AUTONOMOUS:  # noqa: SIM103
            # Low and medium execute automatically, HIGH is already handled above
            return False

        return True

    def create_approval_request(
        self,
        decision: Decision,
        window_hwnd: int | None = None,
        application_name: str = "",
        target_bounds: dict[str, int] | None = None,
        timeout_seconds: float = 120.0,
        display_context: dict[str, Any] | None = None,
    ) -> ApprovalRecord:
        """
        Create a state-bound approval request.
        """
        now = time.time()
        key = f"{decision.task_id}:{decision.decision_id}"

        target_id = ""
        if decision.target:
            target_id = (
                decision.target.automation_id
                or decision.target.runtime_id
                or decision.target.name
                or ""
            )
        if not target_id:
            target_id = decision.target_description

        record = ApprovalRecord(
            approval_id=f"appr_{uuid.uuid4().hex[:10]}",
            task_id=decision.task_id,
            decision_id=decision.decision_id,
            action=decision.action.value,
            action_parameters=dict(decision.parameters or {}),
            target_identifier=target_id,
            target_bounds=target_bounds
            or (decision.target.bounding_rect if decision.target else None),
            window_hwnd=window_hwnd
            or (decision.target.hwnd if decision.target else None),
            application_name=application_name
            or (decision.target.window_title if decision.target else ""),
            observation_timestamp=decision.timestamp or now,
            risk_level=decision.risk_level,
            state=ApprovalState.PENDING,
            created_at=now,
            expires_at=now + timeout_seconds,
            display_context=display_context,
        )
        record.approval_token = compute_action_approval_digest(
            record.task_id,
            record.decision_id,
            record.action,
            record.target_identifier,
            record.action_parameters,
        )
        self._approvals[key] = record
        self._persist_record(record)
        logger.info(
            f"Created approval request [{record.approval_id}] for task [{decision.task_id}] decision [{decision.decision_id}], risk={decision.risk_level.value}"
        )
        return record

    def grant_approval(self, task_id: str, decision_id: str) -> bool:
        """User explicitly grants approval for a pending decision."""
        key = f"{task_id}:{decision_id}"
        record = self._approvals.get(key)
        if not record:
            logger.warning(
                f"Grant approval failed: no approval request found for {key}"
            )
            return False

        if record.state != ApprovalState.PENDING:
            logger.warning(
                f"Grant approval failed: approval {key} is in state {record.state.value}"
            )
            return False

        if time.time() > record.expires_at:
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = "Approval request expired before grant"
            self._persist_record(record)
            return False

        record.state = ApprovalState.GRANTED
        record.granted_at = time.time()
        self._persist_record(record)
        logger.info(f"Approval GRANTED for task [{task_id}] decision [{decision_id}]")
        return True

    def reject_approval(
        self, task_id: str, decision_id: str, reason: str = "User rejected"
    ) -> bool:
        """User explicitly rejects approval."""
        key = f"{task_id}:{decision_id}"
        record = self._approvals.get(key)
        if not record:
            return False

        record.state = ApprovalState.REJECTED
        record.invalidation_reason = reason
        self._persist_record(record)
        logger.info(
            f"Approval REJECTED for task [{task_id}] decision [{decision_id}]: {reason}"
        )
        return True

    def request_approval(
        self,
        decision_id: str,
        task_id: str,
        action_type: str,
        target_description: str,
        explanation: str,
        risk_level: RiskLevel = RiskLevel.HIGH,
        timeout_seconds: float = 60.0,
    ) -> ApprovalRecord:
        """Create a direct approval request for Claude computer-use loop or external callers."""
        now = time.time()
        key = f"{task_id}:{decision_id}"
        record = ApprovalRecord(
            approval_id=f"appr_{uuid.uuid4().hex[:10]}",
            task_id=task_id,
            decision_id=decision_id,
            action=action_type,
            action_parameters={},
            target_identifier=target_description,
            target_bounds=None,
            window_hwnd=None,
            application_name="",
            observation_timestamp=now,
            risk_level=risk_level,
            state=ApprovalState.PENDING,
            created_at=now,
            expires_at=now + timeout_seconds,
            display_context={"explanation": explanation},
        )
        record.approval_token = compute_action_approval_digest(
            record.task_id,
            record.decision_id,
            record.action,
            record.target_identifier,
            record.action_parameters,
        )
        self._approvals[key] = record
        self._persist_record(record)
        logger.info(f"Direct approval requested [{record.approval_id}] for task [{task_id}] action [{action_type}]")
        return record

    def verify_and_consume_approval_digest(
        self,
        task_id: str,
        decision_id: str,
        action_type: str,
        target: str,
        params: dict[str, Any] | None = None,
        approval_token: str = "",
        secret_key: bytes = APPROVAL_SECRET_KEY,
    ) -> tuple[bool, str]:
        """Verify HMAC-SHA256 signature and atomically consume the approval."""
        if not approval_token:
            return False, "Approval token missing"
        expected = compute_action_approval_digest(
            task_id, decision_id, action_type, target, params, secret_key
        )
        if not hmac.compare_digest(expected, approval_token):
            return False, "Approval token digest mismatch"
        return self.consume_approval(task_id, decision_id)

    def get_approval_record(self, approval_id: str) -> ApprovalRecord | None:
        """Retrieve an approval record by its unique approval_id."""
        for rec in self._approvals.values():
            if rec.approval_id == approval_id:
                return rec
        return None

    def list_pending(self) -> list[ApprovalRecord]:
        """List all pending approval records across active tasks."""
        now = time.time()
        return [r for r in self._approvals.values() if r.state == ApprovalState.PENDING and now <= r.expires_at]

    def submit_decision(self, decision_id: str, approved: bool, reason: str = "") -> bool:
        """Submit approval or rejection by decision_id."""
        for rec in list(self._approvals.values()):
            if rec.decision_id == decision_id:
                if approved:
                    return self.grant_approval(rec.task_id, rec.decision_id)
                else:
                    return self.reject_approval(rec.task_id, rec.decision_id, reason=reason)
        return False

    def get_pending_approval_for_task(self, task_id: str) -> ApprovalRecord | None:
        """Find the active pending approval record for a task, if any."""
        now = time.time()
        for key, record in self._approvals.items():
            if key.startswith(f"{task_id}:") and record.state == ApprovalState.PENDING:
                if now <= record.expires_at:
                    return record
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = "Approval request expired"
                self._persist_record(record)
        return None

    def consume_approval(self, task_id: str, decision_id: str) -> tuple[bool, str]:
        """
        Atomically transition GRANTED -> CONSUMED (§4, §9).
        Enforces single-use token semantics and prevents replay.
        """
        key = f"{task_id}:{decision_id}"
        record = self._approvals.get(key)
        if not record:
            return False, "No approval record found for this decision."

        if (
            record.state == ApprovalState.CONSUMED
            or record.approval_id in self._consumed_ids
        ):
            return (
                False,
                "Approval has already been consumed (single-use token replay rejected).",
            )

        if time.time() > record.expires_at:
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = "Approval token expired before consumption."
            self._persist_record(record)
            return False, "Approval token expired before consumption."

        if record.state != ApprovalState.GRANTED:
            return False, f"Cannot consume approval in state: {record.state.value}."

        record.state = ApprovalState.CONSUMED
        record.consumed_at = time.time()
        self._consumed_ids.add(record.approval_id)
        self._persist_record(record)
        logger.info(
            f"Approval [{record.approval_id}] CONSUMED for task [{task_id}] decision [{decision_id}]"
        )
        return True, "Approval successfully consumed."

    def invalidate_all_approvals_for_task(
        self, task_id: str, reason: str = "Task stopped or modified"
    ) -> int:
        """Invalidate all pending/granted approvals for a task."""
        count = 0
        for key, record in list(self._approvals.items()):
            if record.task_id == task_id and record.state in [
                ApprovalState.PENDING,
                ApprovalState.GRANTED,
            ]:
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = reason
                self._persist_record(record)
                count += 1
        return count

    def cleanup_task(self, task_id: str) -> int:
        """Purge all approvals associated with a completed or cleaned task."""
        count = 0
        for key, record in list(self._approvals.items()):
            if record.task_id == task_id:
                del self._approvals[key]
                count += 1
        return count

    def get_approval(self, task_id: str, decision_id: str) -> ApprovalRecord | None:
        key = f"{task_id}:{decision_id}"
        return self._approvals.get(key)

    def get_approval_status(
        self, task_id: str, decision_id: str
    ) -> ApprovalRecord | None:
        key = f"{task_id}:{decision_id}"
        return self._approvals.get(key)

    def validate_approval_binding(
        self,
        task_id: str,
        decision_id: str,
        current_action: PlannerActionType,
        current_target_identifier: str,
        current_hwnd: int | None,
        current_app: str,
        current_bounds: dict[str, int] | None,
        current_parameters: dict[str, Any] | None = None,
        current_display_context: dict[str, Any] | None = None,
        current_time: float | None = None,
        max_observation_age_s: float = 10.0,
    ) -> tuple[bool, str]:
        """
        Comprehensive anti-bypass pre-dispatch verification (Directive §5, §10).
        Compares live execution state against approved state.
        Invalidates approval if anything has drifted.
        """
        now = current_time or time.time()
        key = f"{task_id}:{decision_id}"
        record = self._approvals.get(key)

        if not record:
            return False, "No approval record found for this decision."

        if (
            record.state == ApprovalState.CONSUMED
            or record.approval_id in self._consumed_ids
        ):
            return (
                False,
                "Approval has already been consumed (single-use token replay rejected).",
            )

        if record.state == ApprovalState.PENDING:
            return False, "Approval request is still pending user decision."

        if record.state == ApprovalState.REJECTED:
            return (
                False,
                f"Action rejected by user: {record.invalidation_reason or 'Explicit rejection'}.",
            )

        if record.state == ApprovalState.INVALIDATED:
            return (
                False,
                f"Approval previously invalidated: {record.invalidation_reason}.",
            )

        if record.state != ApprovalState.GRANTED:
            return False, f"Invalid approval state: {record.state.value}."

        # Check task terminal status
        try:
            from backend.app.models import TaskState
            from backend.app.services.task_service import task_service

            t = task_service.get_task(task_id)
            if t and t.state in [
                TaskState.CANCELLED,
                TaskState.COMPLETED,
                TaskState.STOPPED,
                TaskState.FAILED,
            ]:
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = (
                    f"Task [{task_id}] is in terminal state {t.state.value}."
                )
                self._persist_record(record)
                return False, record.invalidation_reason
        except Exception:  # noqa: BLE001, S110
            pass

        # 1. Check expiration
        if now > record.expires_at:
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = "Approval token expired."
            return False, "Approval token expired."

        # 2. Check observation staleness
        if max_observation_age_s and (
            now - record.observation_timestamp > max_observation_age_s
        ):
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = f"Observation became stale ({(now - record.observation_timestamp):.1f}s > {max_observation_age_s}s)."
            return False, record.invalidation_reason

        # 3. Action changed?
        if record.action != current_action.value:
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = (
                f"Action changed from '{record.action}' to '{current_action.value}'."
            )
            return False, record.invalidation_reason

        # 4. Action parameters changed?
        if current_parameters is not None and record.action_parameters:  # noqa: SIM102
            if record.action_parameters != current_parameters:
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = f"Action parameters changed from {record.action_parameters} to {current_parameters}."
                return False, record.invalidation_reason

        # 5. Target identifier changed?
        clean_target = (current_target_identifier or "").strip().lower()
        clean_approved_target = (record.target_identifier or "").strip().lower()
        if (  # noqa: SIM102
            clean_target
            and clean_approved_target
            and clean_target != clean_approved_target
        ):
            if (
                clean_target not in clean_approved_target
                and clean_approved_target not in clean_target
            ):
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = f"Target changed from '{record.target_identifier}' to '{current_target_identifier}'."
                return False, record.invalidation_reason

        # 6. Target disappeared?
        if record.target_bounds is not None and current_bounds is None:
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = (
                "Target UI element disappeared from live application interface."
            )
            return False, record.invalidation_reason

        # 7. Application changed?
        if record.application_name and current_app:
            clean_rec_app = record.application_name.strip().lower()
            clean_cur_app = current_app.strip().lower()
            if (
                clean_rec_app not in clean_cur_app
                and clean_cur_app not in clean_rec_app
            ):
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = f"Application changed from '{record.application_name}' to '{current_app}'."
                return False, record.invalidation_reason

        # 8. Target window HWND changed?
        if record.window_hwnd and current_hwnd and record.window_hwnd != current_hwnd:
            record.state = ApprovalState.INVALIDATED
            record.invalidation_reason = f"Target window HWND changed from {record.window_hwnd} to {current_hwnd}."
            return False, record.invalidation_reason

        # 9. Target bounds moved materially? (> 120 px shift)
        if record.target_bounds and current_bounds:
            orig_x = record.target_bounds.get("left", record.target_bounds.get("x", 0))
            orig_y = record.target_bounds.get("top", record.target_bounds.get("y", 0))
            cur_x = current_bounds.get("left", current_bounds.get("x", 0))
            cur_y = current_bounds.get("top", current_bounds.get("y", 0))
            drift = ((orig_x - cur_x) ** 2 + (orig_y - cur_y) ** 2) ** 0.5
            if drift > 120.0:
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = (
                    f"Target element moved materially ({drift:.1f}px shift)."
                )
                return False, record.invalidation_reason

        # 10. Display context changed?
        if current_display_context is not None and record.display_context:  # noqa: SIM102
            if record.display_context != current_display_context:
                record.state = ApprovalState.INVALIDATED
                record.invalidation_reason = (
                    "Screen display context changed after approval."
                )
                return False, record.invalidation_reason

        return True, "Approval is valid, current, and state-bound."

    def record_approval_response(
        self, task_id: str, decision_id: str, granted: bool, reason: str = ""
    ) -> bool:
        """Record explicit human approval decision (grant or reject)."""
        if granted:
            return self.grant_approval(task_id, decision_id)
        else:
            return self.reject_approval(task_id, decision_id, reason=reason)

    def validate_approval_state(
        self,
        task_id: str,
        decision_id: str,
        current_hwnd: int | None = None,
        current_app_name: str = "",
        current_target_bounds: dict[str, int] | None = None,
        current_action: PlannerActionType | None = None,
        current_target: str | None = None,
        current_parameters: dict[str, Any] | None = None,
        current_display_context: dict[str, Any] | None = None,
        current_time: float | None = None,
    ) -> tuple[bool, str]:
        """Convenience method for anti-bypass state validation."""
        key = f"{task_id}:{decision_id}"
        record = self._approvals.get(key)
        action_val = current_action or (
            PlannerActionType(record.action) if record else PlannerActionType.CLICK
        )
        target_val = current_target or (record.target_identifier if record else "")
        return self.validate_approval_binding(
            task_id=task_id,
            decision_id=decision_id,
            current_action=action_val,
            current_target_identifier=target_val,
            current_hwnd=current_hwnd,
            current_app=current_app_name,
            current_bounds=current_target_bounds,
            current_parameters=current_parameters,
            current_display_context=current_display_context,
            current_time=current_time,
        )


human_approval_controller = HumanApprovalController(
    default_mode=GuidanceMode.AUTONOMOUS
)
