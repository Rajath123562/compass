"""
COMPASS Crash & Restart Recovery Handler (§32)
Audits active tasks on system startup.
Guarantees zero blind action resumption, invalidates stale approvals,
and marks interrupted tasks as STOPPED cleanly.
"""

from __future__ import annotations

from typing import Any

from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.models import TERMINAL_STATES as APP_TERMINAL_STATES
from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.human_approval import human_approval_controller

TERMINAL_STATES = {
    s.value if hasattr(s, "value") else str(s) for s in APP_TERMINAL_STATES
} | {
    TaskState.COMPLETED.value,
    TaskState.TASK_COMPLETED.value,
    TaskState.FAILED.value,
    TaskState.STOPPED.value,
    TaskState.CANCELLED.value,
    TaskState.BLOCKED.value,
    TaskState.UNVERIFIED.value,
    TaskState.AI_UNAVAILABLE.value,
    TaskState.SAFETY_BLOCKED.value,
}


class CrashRecoveryHandler:
    """
    Handles startup recovery for tasks interrupted by application or machine crash.
    """

    def __init__(self):
        pass

    def recover_interrupted_tasks(self) -> list[dict[str, Any]]:
        """
        Audit database on startup for tasks left in non-terminal states.
        Transitions them to STOPPED, invalidates active approvals, and logs recovery events.
        Guarantees that no interrupted action blindly resumes on restart (§32).
        """
        recovered = []
        try:
            with db.connection() as conn:
                cursor = conn.cursor()
                # Find all non-terminal tasks
                cursor.execute("SELECT id, goal, state FROM tasks;")
                rows = cursor.fetchall()

                for row in rows:
                    t_id = row["id"]
                    t_state = row["state"]
                    if t_state not in TERMINAL_STATES:
                        logger.warning(
                            f"CrashRecovery: Task [{t_id}] was left in non-terminal state [{t_state}]. "
                            f"Marking STOPPED to prevent blind action resumption."
                        )
                        # Mark task STOPPED
                        try:
                            task_service.transition_state(
                                task_id=t_id,
                                new_state=TaskState.STOPPED,
                                reason="System restarted; task was interrupted mid-execution",
                            )
                        except Exception:  # noqa: BLE001
                            # Fallback direct DB update if task_service transition fails
                            db.update_task_state(
                                task_id=t_id,
                                new_state=TaskState.STOPPED.value,
                                reason="System restarted; task was interrupted mid-execution",
                            )

                        # Invalidate approvals in memory and in DB
                        human_approval_controller.invalidate_all_approvals_for_task(
                            task_id=t_id,
                            reason="System restarted; task was interrupted mid-execution",
                        )

                        recovered.append(
                            {
                                "task_id": t_id,
                                "previous_state": t_state,
                                "new_state": TaskState.STOPPED.value,
                                "reason": "Interrupted by system restart",
                            }
                        )

                # Invalidate any lingering PENDING or GRANTED approvals in database
                cursor.execute(
                    """
                    UPDATE approvals
                    SET state = 'INVALIDATED',
                        invalidation_reason = 'System restarted; stale approval invalidated'
                    WHERE state IN ('PENDING', 'GRANTED');
                    """
                )

        except Exception as e:  # noqa: BLE001
            logger.error(
                f"CrashRecoveryHandler encountered error during recovery scan: {e}"
            )

        if recovered:
            logger.info(
                f"CrashRecoveryHandler cleaned up {len(recovered)} interrupted task(s)."
            )
        return recovered


crash_recovery_handler = CrashRecoveryHandler()
