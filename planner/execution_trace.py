"""
COMPASS Phase 6 — Structured Execution Trace
Captures detailed, chronological, machine-verifiable task execution traces.
Enforces strict secret and credential redaction across all log and trace records.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.app.logging_config import logger


class StepTraceEntry(BaseModel):
    """Detailed trace of an individual step execution."""

    step_id: str
    goal: str
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    perception_summary: dict[str, Any] | None = None
    action_type: str | None = None
    target_description: str | None = None
    risk_level: str | None = None
    approval_granted: bool = True
    action_dispatched: bool = False
    verification_status: str | None = None
    verification_details: str | None = None
    recovery_invoked: bool = False
    recovery_details: str | None = None
    status: str = "PENDING"
    duration_s: float = 0.0


class ExecutionTrace(BaseModel):
    """Complete machine-readable execution trace for a multi-step task."""

    task_id: str
    goal: str
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    steps: list[StepTraceEntry] = Field(default_factory=list)
    recovery_events: list[dict[str, Any]] = Field(default_factory=list)
    replan_events: list[dict[str, Any]] = Field(default_factory=list)
    stop_events: list[dict[str, Any]] = Field(default_factory=list)
    final_verification: dict[str, Any] | None = None
    final_status: str = "IN_PROGRESS"
    total_duration_s: float = 0.0


class WorkflowExecutionTrace(BaseModel):
    """Phase 8 Complete machine-readable execution trace for an autonomous workflow."""

    workflow_id: str
    task_id: str
    goal: str
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    node_traces: list[StepTraceEntry] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    final_status: str = "IN_PROGRESS"
    total_duration_s: float = 0.0


class ExecutionTraceManager:
    """
    Manages building, redacting, and serializing execution traces.
    """

    SECRET_PATTERNS = [  # noqa: RUF012
        (
            re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~+/]+=*", re.IGNORECASE),
            r"\1[REDACTED_SECRET]",
        ),
        (re.compile(r"(sk-[A-Za-z0-9\-_]{16,})", re.IGNORECASE), "[REDACTED_API_KEY]"),
        (
            re.compile(
                r"(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9\-_]{16,}([\"']?)",
                re.IGNORECASE,
            ),
            r"\1[REDACTED_SECRET]\2",
        ),
        (
            re.compile(
                r"(password[\"']?\s*[:=]\s*[\"']?)[^\"'\s,]{3,}([\"']?)", re.IGNORECASE
            ),
            r"\1[REDACTED_PASSWORD]\2",
        ),
    ]

    def __init__(self, trace_dir: Path | None = None):
        self.trace_dir = trace_dir or Path("artifacts/traces")
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._active_traces: dict[str, ExecutionTrace] = {}
        self._active_workflow_traces: dict[str, WorkflowExecutionTrace] = {}

    def start_trace(self, task_id: str, goal: str) -> ExecutionTrace:
        """Initialize an execution trace for a task."""
        trace = ExecutionTrace(task_id=task_id, goal=self.redact_text(goal))
        self._active_traces[task_id] = trace
        return trace

    def get_trace(self, task_id: str) -> ExecutionTrace | None:
        return self._active_traces.get(task_id)

    def record_step_start(
        self, task_id: str, step_id: str, goal: str
    ) -> StepTraceEntry:
        trace = self._active_traces.get(task_id)
        if not trace:
            trace = self.start_trace(task_id, goal)
        entry = StepTraceEntry(
            step_id=step_id, goal=self.redact_text(goal), status="IN_PROGRESS"
        )
        trace.steps.append(entry)
        return entry

    def record_step_finish(
        self,
        task_id: str,
        step_id: str,
        status: str,
        verification_status: str | None = None,
        verification_details: str | None = None,
    ) -> None:
        trace = self._active_traces.get(task_id)
        if not trace:
            return
        for s in trace.steps:
            if s.step_id == step_id:
                s.end_time = time.time()
                s.status = status
                s.verification_status = verification_status
                s.verification_details = self.redact_text(verification_details or "")
                s.duration_s = round(s.end_time - s.start_time, 3)
                break

    def record_stop_event(self, task_id: str, reason: str) -> None:
        trace = self._active_traces.get(task_id)
        if trace:
            trace.stop_events.append(
                {"timestamp": time.time(), "reason": self.redact_text(reason)}
            )

    def finalize_trace(
        self,
        task_id: str,
        final_status: str,
        final_verification: dict[str, Any] | None = None,
    ) -> Path | None:
        trace = self._active_traces.get(task_id)
        if not trace:
            return None

        trace.end_time = time.time()
        trace.final_status = final_status
        trace.final_verification = self._redact_dict(final_verification or {})
        trace.total_duration_s = round(trace.end_time - trace.start_time, 3)

        out_path = self.trace_dir / f"{task_id}_trace.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(trace.model_dump_json(indent=2))

        self._prune_old_traces(max_retained=100)
        logger.info(f"Finalized execution trace for task [{task_id}] -> {out_path}")
        return out_path

    def _prune_old_traces(self, max_retained: int = 100) -> None:
        try:
            files = sorted(
                self.trace_dir.glob("*_trace.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old_file in files[max_retained:]:
                try:
                    old_file.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed to prune old traces: {e}")

    def redact_text(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        result = text
        for pat, repl in self.SECRET_PATTERNS:
            result = pat.sub(repl, result)
        return result

    def _redact_dict(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._redact_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._redact_dict(item) for item in data]
        elif isinstance(data, str):
            return self.redact_text(data)
        return data

    # -----------------------------------------------------------------------
    # Phase 8: Workflow Execution Trace Operations
    # -----------------------------------------------------------------------

    def start_workflow_trace(
        self, workflow_id: str, task_id: str, goal: str
    ) -> WorkflowExecutionTrace:
        """Initialize an execution trace for an autonomous workflow."""
        trace = WorkflowExecutionTrace(
            workflow_id=workflow_id, task_id=task_id, goal=self.redact_text(goal)
        )
        self._active_workflow_traces[workflow_id] = trace
        self.record_workflow_event(
            workflow_id, "workflow_created", {"task_id": task_id, "goal": goal}
        )
        return trace

    def get_workflow_trace(self, workflow_id: str) -> WorkflowExecutionTrace | None:
        return self._active_workflow_traces.get(workflow_id)

    def record_workflow_event(
        self,
        workflow_id: str,
        event_name: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Record a milestone or lifecycle event in the workflow trace."""
        trace = self._active_workflow_traces.get(workflow_id)
        if trace:
            trace.events.append(
                {
                    "event": event_name,
                    "timestamp": time.time(),
                    "payload": self._redact_dict(payload or {}),
                }
            )

    def record_node_start(
        self, workflow_id: str, node_id: str, goal: str
    ) -> StepTraceEntry:
        """Record node commencement."""
        trace = self._active_workflow_traces.get(workflow_id)
        if not trace:
            trace = self.start_workflow_trace(workflow_id, "unknown", goal)
        entry = StepTraceEntry(
            step_id=node_id, goal=self.redact_text(goal), status="RUNNING"
        )
        trace.node_traces.append(entry)
        self.record_workflow_event(
            workflow_id, "node_started", {"node_id": node_id, "goal": goal}
        )
        return entry

    def record_node_finish(
        self,
        workflow_id: str,
        node_id: str,
        status: str,
        verification_status: str | None = None,
        verification_details: str | None = None,
    ) -> None:
        """Record node completion, verification, and duration."""
        trace = self._active_workflow_traces.get(workflow_id)
        if not trace:
            return
        for n in trace.node_traces:
            if n.step_id == node_id:
                n.end_time = time.time()
                n.status = status
                n.verification_status = verification_status
                n.verification_details = self.redact_text(verification_details or "")
                n.duration_s = round(n.end_time - n.start_time, 3)
                break
        self.record_workflow_event(
            workflow_id,
            f"node_{status.lower()}",
            {
                "node_id": node_id,
                "status": status,
                "verification_status": verification_status,
            },
        )

    def finalize_workflow_trace(
        self, workflow_id: str, final_status: str
    ) -> Path | None:
        """Finalize and serialize workflow trace to disk."""
        trace = self._active_workflow_traces.get(workflow_id)
        if not trace:
            return None

        trace.end_time = time.time()
        trace.final_status = final_status
        trace.total_duration_s = round(trace.end_time - trace.start_time, 3)
        self.record_workflow_event(
            workflow_id, f"workflow_{final_status.lower()}", {"status": final_status}
        )

        out_path = self.trace_dir / f"wf_{workflow_id}_trace.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(trace.model_dump_json(indent=2))

        logger.info(
            f"Finalized workflow execution trace for [{workflow_id}] status={final_status} -> {out_path}"
        )
        return out_path
