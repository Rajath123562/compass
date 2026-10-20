"""
COMPASS Phase 10 — Reliability Monitor & State Reconciliation Subsystem
Provides continuous incident logging, anomaly detection, state reconciliation,
and health aggregation across autonomous execution workflows.
Strictly adheres to Zero-Trust: never invents success states or bypasses locks.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.models import TaskState


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentCategory(str, Enum):
    UI_TARGET_LOST = "UI_TARGET_LOST"
    OBSERVATION_STALE = "OBSERVATION_STALE"
    ACTION_TIMEOUT = "ACTION_TIMEOUT"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    CONCURRENT_STOP = "CONCURRENT_STOP"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    STATE_MISMATCH = "STATE_MISMATCH"
    RESOURCE_THROTTLED = "RESOURCE_THROTTLED"


@dataclass
class IncidentRecord:
    incident_id: str
    task_id: str
    category: IncidentCategory
    severity: IncidentSeverity
    details: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution_notes: str | None = None


class ReliabilityMonitor:
    """
    In-process reliability tracking and reconciliation engine.
    Ensures that failures are recorded with full diagnostic context
    and that memory/database state mismatches are truthfully reconciled.
    """

    def __init__(self):
        self._incidents: list[IncidentRecord] = []
        self._lock = threading.Lock()

    def record_incident(
        self,
        task_id: str,
        category: IncidentCategory,
        severity: IncidentSeverity,
        details: dict[str, Any],
    ) -> IncidentRecord:
        """Record an incident in-memory and log a durable event in SQLite database."""
        inc_id = f"inc_{uuid.uuid4().hex[:8]}"
        record = IncidentRecord(
            incident_id=inc_id,
            task_id=task_id,
            category=category,
            severity=severity,
            details=details,
            timestamp=time.time(),
        )
        with self._lock:
            self._incidents.append(record)
            if len(self._incidents) > 1000:
                self._incidents.pop(0)

        logger.warning(
            f"ReliabilityMonitor logged [{severity.value}] incident [{inc_id}] for task [{task_id}]: "
            f"category={category.value}, details={details}"
        )

        try:
            db.log_task_event(
                task_id=task_id,
                event_type="reliability_incident",
                payload={
                    "incident_id": inc_id,
                    "category": category.value,
                    "severity": severity.value,
                    "details": details,
                    "timestamp": record.timestamp,
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Could not persist incident event to DB: {e}")

        return record

    def get_incidents_for_task(self, task_id: str) -> list[IncidentRecord]:
        with self._lock:
            return [inc for inc in self._incidents if inc.task_id == task_id]

    def reconcile_task_state(
        self, task_id: str, in_memory_stopped: bool
    ) -> tuple[bool, str]:
        """
        Reconciles database task state against in-memory execution status.
        If a task is stopped in memory but left in a transitional state in DB,
        reconciles DB to STOPPED. Never fabricates COMPLETED.
        """
        task = db.get_task(task_id)
        if not task:
            return False, f"Task '{task_id}' not found in database."

        db_state = task.get("state")

        # If in-memory STOP was asserted but DB is in a transitional state
        if in_memory_stopped and db_state in [
            TaskState.STARTING.value,
            TaskState.UNDERSTANDING.value,
            TaskState.OBSERVING.value,
            TaskState.PLANNING.value,
            TaskState.DECIDING.value,
            TaskState.VALIDATING.value,
            TaskState.ACTING.value,
            TaskState.VERIFYING.value,
            TaskState.RECOVERING.value,
            TaskState.REPLANNING.value,
        ]:
            db.update_task_state(
                task_id,
                TaskState.STOPPED.value,
                reason="Reconciled to STOPPED by ReliabilityMonitor",
            )
            self.record_incident(
                task_id=task_id,
                category=IncidentCategory.STATE_MISMATCH,
                severity=IncidentSeverity.MEDIUM,
                details={
                    "previous_state": db_state,
                    "reconciled_state": TaskState.STOPPED.value,
                },
            )
            return (
                True,
                f"Reconciled task '{task_id}' from '{db_state}' to '{TaskState.STOPPED.value}'",
            )

        return True, f"Task '{task_id}' state '{db_state}' is consistent."

    def clear_all(self):
        with self._lock:
            self._incidents.clear()


reliability_monitor = ReliabilityMonitor()
