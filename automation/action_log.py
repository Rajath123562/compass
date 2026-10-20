"""
COMPASS Action Audit Log
SQLite-backed persistent audit log for all automation actions.

Privacy: For type actions, only length and success/failure are stored.
         Actual text content is NEVER persisted.
"""

import json
import time
from typing import Any

from backend.app.database import db
from backend.app.logging_config import logger

ACTION_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS action_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       TEXT,
    timestamp     REAL NOT NULL,
    action_type   TEXT NOT NULL,
    target_hwnd   INTEGER,
    target_name   TEXT,
    target_automation_id TEXT,
    target_control_type  TEXT,
    window_title  TEXT,
    execution_method TEXT,
    parameters_meta TEXT DEFAULT '{}',
    result        TEXT,
    error         TEXT,
    duration_ms   REAL
);
CREATE INDEX IF NOT EXISTS idx_action_log_timestamp ON action_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_action_log_task ON action_log(task_id);
"""


def ensure_action_log_table() -> None:
    """Create the action_log table if it doesn't exist."""
    try:
        with db.connection() as conn:
            conn.executescript(ACTION_LOG_SCHEMA)
    except Exception as e:
        logger.error(f"Failed to create action_log table: {e}")
        raise


def log_action(
    action_type: str,
    target_element: dict[str, Any] | None,
    execution_method: str,
    success: bool,
    error: str | None = None,
    duration_ms: float = 0.0,
    task_id: str | None = None,
    parameters_meta: dict[str, Any] | None = None,
) -> int | None:
    """
    Persist an action audit record to SQLite.

    Privacy rules:
      - For 'type' actions, parameters_meta should contain ONLY text_length, NOT the text.
      - Sensitive text content must never be passed in parameters_meta.

    Returns:
        Inserted row ID, or None on failure.
    """
    try:
        now = time.time()
        hwnd = target_element.get("hwnd", 0) if target_element else 0
        name = target_element.get("name", "") if target_element else ""
        auto_id = target_element.get("automation_id", "") if target_element else ""
        ct = target_element.get("control_type", "") if target_element else ""
        title = target_element.get("window_title", "") if target_element else ""

        meta_json = json.dumps(parameters_meta or {})
        result_str = "success" if success else "failure"

        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO action_log
                   (task_id, timestamp, action_type, target_hwnd, target_name,
                    target_automation_id, target_control_type, window_title,
                    execution_method, parameters_meta, result, error, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    now,
                    action_type,
                    hwnd,
                    name,
                    auto_id,
                    ct,
                    title,
                    execution_method,
                    meta_json,
                    result_str,
                    error,
                    duration_ms,
                ),
            )
            return cursor.lastrowid
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to log action: {e}")
        return None


def get_recent_logs(
    limit: int = 50, task_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Return recent action log entries, newest first.

    Args:
        limit:   Maximum entries to return (default 50).
        task_id: If specified, filter to entries for this task.
    """
    try:
        with db.connection() as conn:
            cursor = conn.cursor()
            if task_id:
                cursor.execute(
                    "SELECT * FROM action_log WHERE task_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (task_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM action_log ORDER BY timestamp DESC LIMIT ?", (limit,)
                )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "task_id": r["task_id"],
                    "timestamp": r["timestamp"],
                    "action_type": r["action_type"],
                    "target_hwnd": r["target_hwnd"],
                    "target_name": r["target_name"],
                    "target_automation_id": r["target_automation_id"],
                    "target_control_type": r["target_control_type"],
                    "window_title": r["window_title"],
                    "execution_method": r["execution_method"],
                    "parameters_meta": json.loads(r["parameters_meta"] or "{}"),
                    "result": r["result"],
                    "error": r["error"],
                    "duration_ms": r["duration_ms"],
                }
                for r in rows
            ]
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to retrieve action logs: {e}")
        return []
