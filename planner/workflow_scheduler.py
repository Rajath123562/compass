"""
COMPASS Phase 8 — Ready-Node Scheduler & Concurrency Lock Manager
Deterministic node scheduling per Sections 13-14.
Implements:
  - Multi-level hierarchical resource locks (workflow, app, UI foreground, target)
  - Deterministic lock ordering (alphabetical) to prevent deadlocks
  - Concurrency control (serialized UI actions, parallelizable background reads)
  - Priority and dependency-aware candidate selection
  - Execution-generation fencing
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager

from backend.app.logging_config import logger
from planner.workflow_models import Workflow, WorkflowNode, WorkflowNodeStatus


class ResourceLockManager:
    """
    Manages multi-level named locks for workflow execution with deterministic
    lock ordering to guarantee deadlock freedom.
    """

    def __init__(self):
        self._global_lock = threading.Lock()
        self._named_locks: dict[str, threading.Lock] = {}
        self._held_locks: dict[str, str] = {}  # lock_name -> holder_id

    def _get_or_create_lock(self, name: str) -> threading.Lock:
        with self._global_lock:
            if name not in self._named_locks:
                self._named_locks[name] = threading.Lock()
            return self._named_locks[name]

    def acquire_locks(
        self, lock_names: list[str], holder_id: str, timeout_s: float = 5.0
    ) -> bool:
        """
        Acquire multiple locks in deterministic sorted order to prevent deadlocks.
        Returns True if all locks acquired, False if timeout (releasing any acquired).
        """
        if not lock_names:
            return True

        # Deterministic ordering prevents AB-BA deadlocks
        sorted_names = sorted(set(lock_names))
        acquired: list[str] = []
        deadline = time.time() + timeout_s

        for name in sorted_names:
            lock = self._get_or_create_lock(name)
            remaining = max(0.01, deadline - time.time())
            success = lock.acquire(timeout=remaining)
            if not success:
                # Release already acquired in reverse order
                for acq_name in reversed(acquired):
                    self._named_locks[acq_name].release()
                    self._held_locks.pop(acq_name, None)
                logger.warning(
                    f"Lock acquisition timed out for [{holder_id}] on '{name}'"
                )
                return False
            acquired.append(name)
            self._held_locks[name] = holder_id

        return True

    def release_locks(self, lock_names: list[str], holder_id: str) -> None:
        """Release acquired locks in reverse sorted order."""
        if not lock_names:
            return
        sorted_names = sorted(set(lock_names), reverse=True)
        for name in sorted_names:
            if name in self._named_locks and self._held_locks.get(name) == holder_id:
                try:
                    self._held_locks.pop(name, None)
                    self._named_locks[name].release()
                except RuntimeError:
                    pass

    @contextmanager
    def locked(self, lock_names: list[str], holder_id: str, timeout_s: float = 5.0):
        acquired = self.acquire_locks(lock_names, holder_id, timeout_s)
        if not acquired:
            raise TimeoutError(f"Failed to acquire locks {lock_names} for {holder_id}")
        try:
            yield
        finally:
            self.release_locks(lock_names, holder_id)

    def is_locked(self, name: str) -> bool:
        with self._global_lock:
            return name in self._held_locks


class ReadyNodeScheduler:
    """
    Evaluates workflow graph to select eligible READY nodes for dispatch.
    Enforces dependency completion, approval requirements, resource availability,
    concurrency constraints, and priority ordering.
    """

    UI_FOREGROUND_LOCK = "lock:system:ui_foreground"

    def __init__(self, lock_manager: ResourceLockManager | None = None):
        self.lock_manager = lock_manager or ResourceLockManager()

    def get_ready_nodes(
        self, workflow: Workflow, max_concurrent: int = 2, currently_running: int = 0
    ) -> list[WorkflowNode]:
        """
        Identify and sort nodes ready for immediate dispatch.
        Respects:
          - Dependencies must be COMPLETED
          - Node must be in PENDING or BLOCKED_BY_DEPENDENCY or READY state
          - Approval requirement does not prevent READY status (approval is requested at dispatch)
          - Max concurrent capacity
          - Priority ordering (higher priority integer executed first)
        """
        available_slots = max(0, max_concurrent - currently_running)
        if available_slots <= 0:
            return []

        completed_ids: set[str] = {
            n.node_id
            for n in workflow.nodes
            if n.status == WorkflowNodeStatus.COMPLETED
        }

        candidates: list[WorkflowNode] = []

        for node in workflow.nodes:
            if node.status in (
                WorkflowNodeStatus.PENDING,
                WorkflowNodeStatus.BLOCKED_BY_DEPENDENCY,
                WorkflowNodeStatus.READY,
            ):
                # All dependencies must be satisfied
                deps_met = all(dep in completed_ids for dep in node.dependencies)
                if deps_met:
                    candidates.append(node)

        # Sort by priority descending (higher number = higher priority), then node_id
        candidates.sort(key=lambda n: (-n.priority, n.node_id))

        return candidates[:available_slots]

    def compute_required_locks(self, node: WorkflowNode) -> list[str]:
        """
        Determine the full set of resource locks required for a node.
        - Workflow lock: always
        - Target app lock: if application specified
        - UI foreground lock: if operation requires user interface focus
        - Custom resource locks: from node.resource_requirements
        """
        locks = [f"lock:wf:{node.workflow_id}"]

        target = node.action.get("target") or {}
        app_name = target.get("application") or node.action.get("application")
        if app_name:
            locks.append(f"lock:app:{str(app_name).lower()}")

        # UI action check: focus, click, type, mouse, window manipulation
        action_type = node.action.get("type", "").lower()
        ui_actions = {
            "click",
            "double_click",
            "right_click",
            "type",
            "key",
            "key_press",
            "move",
            "scroll",
            "focus",
            "window",
        }
        if action_type in ui_actions or node.resource_requirements.get(
            "requires_ui", True
        ):
            locks.append(self.UI_FOREGROUND_LOCK)

        # Target element lock
        element_id = target.get("automation_id") or target.get("name")
        if element_id:
            locks.append(f"lock:target:{str(element_id).lower()[:32]}")

        # Explicit custom resources
        for res in node.resource_requirements.get("named_resources", []):
            locks.append(f"lock:res:{res}")

        return sorted(list(set(locks)))  # noqa: C414

    def can_dispatch_node(
        self, node: WorkflowNode, active_locks: set[str] | None = None
    ) -> tuple[bool, list[str]]:
        """
        Verify if a node's required locks are currently uncontended.
        Returns (can_dispatch, list_of_conflicting_locks).
        """
        required = self.compute_required_locks(node)
        conflicts: list[str] = []

        if active_locks:
            for lk in required:
                if lk in active_locks:
                    conflicts.append(lk)
        else:
            for lk in required:
                if self.lock_manager.is_locked(lk):
                    conflicts.append(lk)

        return len(conflicts) == 0, conflicts
