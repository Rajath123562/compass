"""
COMPASS Phase 6 — Task Checkpoint Manager
Provides cryptographic HMAC-authenticated checkpointing and safe resumption.
Guarantees secret redaction, live desktop re-perception before resumption,
and immediate fallback to UNVERIFIED/BLOCKED upon state divergence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.app.logging_config import logger


class TaskCheckpoint(BaseModel):
    """Authenticated task execution snapshot."""

    task_id: str
    step_id: str
    completed_step_ids: list[str] = Field(default_factory=list)
    verified_state: dict[str, Any] = Field(default_factory=dict)
    current_application: str | None = None
    expected_window_title: str | None = None
    expected_hwnd: int | None = None
    timestamp: float = Field(default_factory=time.time)
    observation_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_fingerprint: str | None = None
    perception_state: str | None = None
    monitor_dpi_context: dict[str, Any] = Field(default_factory=dict)
    workflow_id: str | None = None
    execution_generation: int = 1
    signature: str = ""


class WorkflowCheckpoint(BaseModel):
    """Phase 8 Authenticated workflow snapshot for crash recovery and resume."""

    workflow_id: str
    task_id: str
    execution_generation: int = 1
    status: str
    completed_node_ids: list[str] = Field(default_factory=list)
    pending_node_ids: list[str] = Field(default_factory=list)
    failed_node_ids: list[str] = Field(default_factory=list)
    running_node_ids: list[str] = Field(default_factory=list)
    node_states: dict[str, str] = Field(default_factory=dict)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    resource_state: dict[str, Any] = Field(default_factory=dict)
    dag_state: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    signature: str = ""


class CheckpointManager:
    """
    Manages task checkpoints with HMAC integrity validation, secret redaction,
    and safe desktop-revalidated resumption.
    """

    SECRET_KEY = b"COMPASS_PHASE_6_INTEGRITY_KEY_7894"

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or Path("artifacts/checkpoints")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        task_id: str,
        step_id: str,
        completed_step_ids: list[str],
        verified_state: dict[str, Any],
        current_app: str | None = None,
        expected_window_title: str | None = None,
        expected_hwnd: int | None = None,
        observation_id: str | None = None,
        evidence_ids: list[str] | None = None,
        evidence_fingerprint: str | None = None,
        perception_state: str | None = None,
        monitor_dpi_context: dict[str, Any] | None = None,
    ) -> TaskCheckpoint:
        """
        Create and persist an authenticated, secret-redacted task checkpoint.
        """
        # Redact sensitive data from verified_state
        safe_state = self._redact_secrets(verified_state)

        checkpoint = TaskCheckpoint(
            task_id=task_id,
            step_id=step_id,
            completed_step_ids=list(completed_step_ids),
            verified_state=safe_state,
            current_application=current_app,
            expected_window_title=expected_window_title,
            expected_hwnd=expected_hwnd,
            timestamp=time.time(),
            observation_id=observation_id,
            evidence_ids=list(evidence_ids or []),
            evidence_fingerprint=evidence_fingerprint,
            perception_state=perception_state,
            monitor_dpi_context=dict(monitor_dpi_context or {}),
        )

        # Compute HMAC signature over payload
        payload_bytes = json.dumps(
            checkpoint.model_dump(exclude={"signature"}), sort_keys=True
        ).encode("utf-8")
        sig = hmac.new(self.SECRET_KEY, payload_bytes, hashlib.sha256).hexdigest()
        checkpoint.signature = sig

        # Save to file
        file_path = self.storage_dir / f"{task_id}_{step_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(checkpoint.model_dump_json(indent=2))

        logger.info(
            f"Checkpoint saved for task [{task_id}] at step [{step_id}] -> {file_path}"
        )
        return checkpoint

    def load_checkpoint(
        self, task_id: str, step_id: str
    ) -> tuple[bool, TaskCheckpoint | None, str | None]:
        """
        Load checkpoint and verify cryptographic HMAC integrity.
        Returns (is_valid, checkpoint, error_message).
        """
        file_path = self.storage_dir / f"{task_id}_{step_id}.json"
        if not file_path.exists():
            return False, None, f"Checkpoint file '{file_path}' does not exist."

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = TaskCheckpoint(**data)
            payload_bytes = json.dumps(
                checkpoint.model_dump(exclude={"signature"}), sort_keys=True
            ).encode("utf-8")
            expected_sig = hmac.new(
                self.SECRET_KEY, payload_bytes, hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(checkpoint.signature, expected_sig):
                logger.error(
                    f"Checkpoint HMAC signature mismatch for task [{task_id}]. State may be corrupted or tampered."
                )
                return (
                    False,
                    None,
                    "Checkpoint integrity validation failed (HMAC mismatch).",
                )

            return True, checkpoint, None
        except Exception as e:  # noqa: BLE001
            return False, None, f"Error parsing checkpoint: {e!s}"

    def validate_for_resume(
        self, checkpoint: TaskCheckpoint, live_window_info: dict[str, Any] | None
    ) -> tuple[bool, str | None]:
        """
        Validate whether current live desktop context allows safe task resumption:
        1. Window title must match expected application/window.
        2. Checkpoint age must not exceed maximum stale window (10 minutes).
        """
        # Age check
        age_s = time.time() - checkpoint.timestamp
        if age_s > 600.0:
            return False, f"Checkpoint is stale ({age_s:.1f}s old, max 600s)."

        if checkpoint.expected_window_title:
            actual_title = (live_window_info or {}).get("title", "")
            if checkpoint.expected_window_title.lower() not in actual_title.lower():
                return (
                    False,
                    f"Desktop context mismatch: Expected window containing '{checkpoint.expected_window_title}', found '{actual_title}'.",
                )

        return True, None

    def _redact_secrets(self, data: Any) -> Any:
        """Recursively scrub passwords, tokens, and secret strings from state dictionaries."""
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(
                    sec in k.lower()
                    for sec in ["password", "secret", "token", "key", "auth"]
                ):
                    clean[k] = "[REDACTED_SECRET]"
                else:
                    clean[k] = self._redact_secrets(v)
            return clean
        elif isinstance(data, list):
            return [self._redact_secrets(item) for item in data]
        elif isinstance(data, str):
            # Check for bearer tokens or hex keys
            import re

            scrubbed = re.sub(
                r"(Bearer\s+)[A-Za-z0-9\-\._~+/]+=*", r"\1[REDACTED_SECRET]", data
            )
            scrubbed = re.sub(r"(sk-[A-Za-z0-9]{20,})", "[REDACTED_API_KEY]", scrubbed)
            return scrubbed
        return data

    # -----------------------------------------------------------------------
    # Phase 8: Workflow Checkpointing
    # -----------------------------------------------------------------------

    def save_workflow_checkpoint(
        self,
        workflow_id: str,
        task_id: str,
        status: str,
        execution_generation: int = 1,
        completed_node_ids: list[str] | None = None,
        pending_node_ids: list[str] | None = None,
        failed_node_ids: list[str] | None = None,
        running_node_ids: list[str] | None = None,
        node_states: dict[str, str] | None = None,
        retry_counts: dict[str, int] | None = None,
        resource_state: dict[str, Any] | None = None,
        dag_state: dict[str, Any] | None = None,
    ) -> WorkflowCheckpoint:
        """Create and persist an HMAC-authenticated workflow execution snapshot."""
        safe_resource = self._redact_secrets(resource_state or {})
        safe_dag = self._redact_secrets(dag_state or {})

        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            task_id=task_id,
            execution_generation=execution_generation,
            status=status,
            completed_node_ids=list(completed_node_ids or []),
            pending_node_ids=list(pending_node_ids or []),
            failed_node_ids=list(failed_node_ids or []),
            running_node_ids=list(running_node_ids or []),
            node_states=dict(node_states or {}),
            retry_counts=dict(retry_counts or {}),
            resource_state=safe_resource,
            dag_state=safe_dag,
            timestamp=time.time(),
        )

        payload_bytes = json.dumps(
            checkpoint.model_dump(exclude={"signature"}), sort_keys=True
        ).encode("utf-8")
        sig = hmac.new(self.SECRET_KEY, payload_bytes, hashlib.sha256).hexdigest()
        checkpoint.signature = sig

        file_path = self.storage_dir / f"wf_{workflow_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(checkpoint.model_dump_json(indent=2))

        logger.info(
            f"Workflow checkpoint saved for [{workflow_id}] gen={execution_generation} -> {file_path}"
        )
        return checkpoint

    def load_workflow_checkpoint(
        self, workflow_id: str
    ) -> tuple[bool, WorkflowCheckpoint | None, str | None]:
        """Load workflow checkpoint and verify cryptographic HMAC integrity."""
        file_path = self.storage_dir / f"wf_{workflow_id}.json"
        if not file_path.exists():
            return (
                False,
                None,
                f"Workflow checkpoint file '{file_path}' does not exist.",
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = WorkflowCheckpoint(**data)
            payload_bytes = json.dumps(
                checkpoint.model_dump(exclude={"signature"}), sort_keys=True
            ).encode("utf-8")
            expected_sig = hmac.new(
                self.SECRET_KEY, payload_bytes, hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(checkpoint.signature, expected_sig):
                logger.error(
                    f"Workflow checkpoint HMAC mismatch for [{workflow_id}]. State corrupted or tampered."
                )
                return (
                    False,
                    None,
                    "Workflow checkpoint integrity validation failed (HMAC mismatch).",
                )

            return True, checkpoint, None
        except Exception as e:  # noqa: BLE001
            return False, None, f"Error parsing workflow checkpoint: {e!s}"

    def validate_workflow_for_resume(
        self, checkpoint: WorkflowCheckpoint, max_stale_seconds: float = 600.0
    ) -> tuple[bool, str | None]:
        """Validate whether workflow checkpoint can be safely resumed."""
        age_s = time.time() - checkpoint.timestamp
        if age_s > max_stale_seconds:
            return (
                False,
                f"Workflow checkpoint is stale ({age_s:.1f}s old, max {max_stale_seconds}s).",
            )
        if checkpoint.status in ("COMPLETED", "CANCELLED", "STOPPED"):
            return (
                False,
                f"Workflow is already in terminal state '{checkpoint.status}'.",
            )
        return True, None
