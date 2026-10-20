"""
COMPASS Task Service
Manages task lifecycle, state transitions, and event logging.
"""

import uuid
from typing import Any

from fastapi import HTTPException

from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.models import TERMINAL_STATES, VALID_TRANSITIONS, TaskState


class TaskService:
    @staticmethod
    def create_task(
        goal: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        # Real initial state for new task request: STARTING
        initial_state = TaskState.STARTING.value
        task = db.create_task(
            task_id=task_id,
            goal=goal.strip(),
            initial_state=initial_state,
            metadata=metadata or {},
        )
        logger.info(f"Created task [{task_id}] with goal: '{goal}'")
        return task

    @staticmethod
    def get_task(task_id: str) -> dict[str, Any]:
        task = db.get_task(task_id)
        if not task:
            if task_id.startswith("chat-"):
                import time
                now = time.time()
                return {
                    "id": task_id,
                    "goal": "Interactive Chat Guidance",
                    "state": TaskState.COMPLETED.value,
                    "created_at": now,
                    "updated_at": now,
                    "metadata": {"guidance_mode": "chat"},
                }
            raise HTTPException(
                status_code=404, detail=f"Task with ID '{task_id}' not found."
            )
        return task

    @staticmethod
    def get_task_detail(task_id: str) -> dict[str, Any]:
        task = TaskService.get_task(task_id)
        events = db.get_task_events(task_id) if not task_id.startswith("chat-") else []
        task["events"] = events
        return task

    @staticmethod
    def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
        return db.list_tasks(limit=limit)

    @staticmethod
    def transition_state(
        task_id: str, new_state: TaskState, reason: str = ""
    ) -> dict[str, Any]:
        task = TaskService.get_task(task_id)
        current_state = TaskState(task["state"])

        # Validate transition against strict state machine
        allowed = VALID_TRANSITIONS.get(current_state, [])
        if new_state not in allowed:
            error_msg = (
                f"Invalid state transition from '{current_state.value}' to '{new_state.value}'. "
                f"Allowed target states: {[s.value for s in allowed]}"
            )
            logger.warning(f"Task [{task_id}] transition rejected: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        updated = db.update_task_state(task_id, new_state.value, reason=reason)
        if not updated:
            raise HTTPException(
                status_code=404,
                detail=f"Task with ID '{task_id}' not found during transition.",
            )
        logger.info(
            f"Task [{task_id}] transitioned from {current_state.value} -> {new_state.value} (reason: {reason})"
        )
        return updated

    @staticmethod
    def stop_task(task_id: str, reason: str = "User requested stop") -> dict[str, Any]:
        task = TaskService.get_task(task_id)
        current_state = TaskState(task["state"])

        if current_state == TaskState.STOPPED:
            return task  # Already stopped - idempotent

        if current_state in TERMINAL_STATES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot stop a task that has already reached terminal state '{current_state.value}'.",
            )

        updated = db.update_task_state(task_id, TaskState.STOPPED.value, reason=reason)
        logger.info(f"Task [{task_id}] was stopped: {reason}")
        return updated

    @staticmethod
    def delete_task(task_id: str) -> dict[str, Any]:
        task = TaskService.get_task(task_id)
        # Attempt to stop execution if running
        try:
            from planner.execution_engine import execution_engine
            execution_engine.stop_task(task_id=task_id, reason="Task deleted by user")
        except Exception:
            pass

        deleted = db.delete_task(task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' could not be deleted.")
        logger.info(f"Task [{task_id}] successfully deleted.")
        return {"status": "deleted", "id": task_id}

    @staticmethod
    def clear_completed_tasks() -> dict[str, Any]:
        count = db.clear_completed_tasks()
        logger.info(f"Cleared {count} completed/terminal tasks.")
        return {"status": "cleared", "deleted_count": count}


task_service = TaskService()
