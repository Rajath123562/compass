"""
COMPASS Database Layer
SQLite persistence with Write-Ahead Logging (WAL) and thread-safe connections.
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from backend.app.config import settings
from backend.app.logging_config import logger

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    timestamp REAL NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_identifier TEXT,
    risk_level TEXT,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    granted_at REAL,
    consumed_at REAL,
    expires_at REAL NOT NULL,
    invalidation_reason TEXT,
    payload TEXT DEFAULT '{}',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    observation_id TEXT,
    action TEXT NOT NULL,
    target_description TEXT,
    risk_level TEXT,
    confidence TEXT,
    requires_confirmation INTEGER,
    created_at REAL NOT NULL,
    payload TEXT DEFAULT '{}',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    execution_generation INTEGER DEFAULT 1,
    resource_budget TEXT DEFAULT '{}',
    deadline REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS workflow_nodes (
    node_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    dependencies TEXT DEFAULT '[]',
    attempt_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}',
    PRIMARY KEY (node_id, workflow_id),
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_task_time ON task_events(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_approvals_task ON approvals(task_id);
CREATE INDEX IF NOT EXISTS idx_approvals_task_state ON approvals(task_id, state);
CREATE INDEX IF NOT EXISTS idx_decisions_task ON decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_workflows_task ON workflows(task_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
CREATE INDEX IF NOT EXISTS idx_nodes_workflow ON workflow_nodes(workflow_id);
CREATE INDEX IF NOT EXISTS idx_nodes_wf_status ON workflow_nodes(workflow_id, status);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    node_id TEXT,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS incident_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    timestamp REAL NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS repair_plans (
    repair_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    status TEXT NOT NULL,
    proposed_diff TEXT,
    human_approval_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_repair_plans_incident ON repair_plans(incident_id);
"""

ALLOWED_WORKFLOW_COLUMNS = {
    "task_id",
    "goal",
    "status",
    "execution_generation",
    "resource_budget",
    "deadline",
    "created_at",
    "updated_at",
    "metadata",
}

ALLOWED_WORKFLOW_NODE_COLUMNS = {
    "goal",
    "status",
    "dependencies",
    "attempt_count",
    "created_at",
    "updated_at",
    "metadata",
}


class DatabaseManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or settings.database_path)
        self._initialized = False

    def get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    @contextmanager
    def connection(self):
        # Auto-initialize schema if not done yet
        if not self._initialized:
            self.init_db()
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error during transaction: {e}")
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.get_connection()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript(SCHEMA_SQL)
            conn.commit()

            from backend.app.migrations import run_migrations
            run_migrations(conn)

            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
        finally:
            conn.close()

    def check_health(self) -> dict[str, Any]:
        """Perform a real read/write check to verify DB health."""
        try:
            start_t = time.time()
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode;")
                mode_row = cursor.fetchone()
                mode = mode_row[0] if mode_row else "unknown"

                test_key = "__health_check__"
                now = time.time()
                cursor.execute(
                    "INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
                    (test_key, "ok", now),
                )
                cursor.execute(
                    "SELECT value FROM system_settings WHERE key = ?;", (test_key,)
                )
                row = cursor.fetchone()
                if not row or row["value"] != "ok":
                    return {
                        "status": "unhealthy",
                        "error": "Read-after-write verification mismatch",
                        "latency_ms": round((time.time() - start_t) * 1000, 2),
                    }

                cursor.execute("SELECT COUNT(*) AS c FROM tasks;")
                count_row = cursor.fetchone()
                task_count = count_row["c"] if count_row else 0

            latency_ms = round((time.time() - start_t) * 1000, 2)
            return {
                "status": "healthy",
                "journal_mode": mode,
                "task_count": task_count,
                "latency_ms": latency_ms,
                "db_path": str(self.db_path),
            }
        except Exception as e:  # noqa: BLE001
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "db_path": str(self.db_path),
            }

    # Task CRUD
    def create_task(
        self,
        task_id: str,
        goal: str,
        initial_state: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        meta_json = json.dumps(metadata or {})
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, goal, state, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?);",
                (task_id, goal, initial_state, now, now, meta_json),
            )
            conn.execute(
                "INSERT INTO task_events (task_id, event_type, payload, timestamp) VALUES (?, ?, ?, ?);",
                (
                    task_id,
                    "TASK_CREATED",
                    json.dumps({"goal": goal, "state": initial_state}),
                    now,
                ),
            )
        return {
            "id": task_id,
            "goal": goal,
            "state": initial_state,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "goal": row["goal"],
                "state": row["state"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": json.loads(row["metadata"] or "{}"),
            }

    def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?;", (limit,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "goal": r["goal"],
                    "state": r["state"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "metadata": json.loads(r["metadata"] or "{}"),
                }
                for r in rows
            ]

    def update_task_state(
        self, task_id: str, new_state: str, reason: str = ""
    ) -> dict[str, Any] | None:
        now = time.time()
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
            existing = cursor.fetchone()
            if not existing:
                return None
            old_state = existing["state"]
            cursor.execute(
                "UPDATE tasks SET state = ?, updated_at = ? WHERE id = ?;",
                (new_state, now, task_id),
            )
            payload = json.dumps(
                {"old_state": old_state, "new_state": new_state, "reason": reason}
            )
            cursor.execute(
                "INSERT INTO task_events (task_id, event_type, payload, timestamp) VALUES (?, ?, ?, ?);",
                (task_id, "STATE_TRANSITION", payload, now),
            )
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and cascade its associated workflow records."""
        with self.connection() as conn:
            conn.execute("DELETE FROM workflows WHERE task_id = ?;", (task_id,))
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
            return cursor.rowcount > 0

    def clear_completed_tasks(self) -> int:
        """Delete all tasks in terminal states (COMPLETED, FAILED, STOPPED, CANCELLED, BLOCKED, etc.)."""
        terminal_states = (
            "COMPLETED",
            "TASK_COMPLETED",
            "FAILED",
            "STOPPED",
            "CANCELLED",
            "BLOCKED",
            "SAFETY_BLOCKED",
            "UNVERIFIED",
            "AI_UNAVAILABLE",
        )
        placeholders = ",".join("?" for _ in terminal_states)
        with self.connection() as conn:
            conn.execute(
                f"DELETE FROM workflows WHERE task_id IN (SELECT id FROM tasks WHERE state IN ({placeholders}));",  # nosec B608
                terminal_states,
            )
            cursor = conn.execute(
                f"DELETE FROM tasks WHERE state IN ({placeholders});",  # nosec B608
                terminal_states,
            )
            return cursor.rowcount

    def get_task_events(self, task_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, task_id, event_type, payload, timestamp FROM task_events WHERE task_id = ? ORDER BY timestamp ASC;",
                (task_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "task_id": r["task_id"],
                    "event_type": r["event_type"],
                    "payload": json.loads(r["payload"] or "{}"),
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]

    def log_task_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
        timestamp: float | None = None,
    ) -> int:
        now = timestamp or time.time()
        payload_json = json.dumps(payload)
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO task_events (task_id, event_type, payload, timestamp) VALUES (?, ?, ?, ?);",
                (task_id, event_type, payload_json, now),
            )
            return cursor.lastrowid or 0

    # Approval & Decision Persistence (§7, §32)
    def save_approval(self, record: dict[str, Any]) -> None:
        with self.connection() as conn:
            # Ensure task exists to satisfy foreign key integrity
            now_t = time.time()
            conn.execute(
                "INSERT OR IGNORE INTO tasks (id, goal, state, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?);",
                (record["task_id"], "Task stub", "CREATED", now_t, now_t, "{}"),
            )
            payload = json.dumps(record.get("payload") or {})
            conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, task_id, decision_id, action, target_identifier,
                    risk_level, state, created_at, granted_at, consumed_at,
                    expires_at, invalidation_reason, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(approval_id) DO UPDATE SET
                    state=excluded.state,
                    granted_at=excluded.granted_at,
                    consumed_at=excluded.consumed_at,
                    invalidation_reason=excluded.invalidation_reason,
                    payload=excluded.payload;
                """,
                (
                    record["approval_id"],
                    record["task_id"],
                    record["decision_id"],
                    record["action"],
                    record.get("target_identifier", ""),
                    record.get("risk_level", ""),
                    record["state"],
                    record.get("created_at", time.time()),
                    record.get("granted_at"),
                    record.get("consumed_at"),
                    record.get("expires_at", time.time() + 120.0),
                    record.get("invalidation_reason"),
                    payload,
                ),
            )

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM approvals WHERE approval_id = ?;", (approval_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["payload"] = json.loads(d.get("payload") or "{}")
            return d

    def get_approval_by_decision(
        self, task_id: str, decision_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM approvals WHERE task_id = ? AND decision_id = ? ORDER BY created_at DESC LIMIT 1;",
                (task_id, decision_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["payload"] = json.loads(d.get("payload") or "{}")
            return d

    def list_approvals_for_task(self, task_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM approvals WHERE task_id = ? ORDER BY created_at ASC;",
                (task_id,),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d.get("payload") or "{}")
                results.append(d)
            return results

    def update_approval_state(
        self,
        approval_id: str,
        state: str,
        reason: str | None = None,
        granted_at: float | None = None,
        consumed_at: float | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE approvals
                SET state = ?,
                    invalidation_reason = COALESCE(?, invalidation_reason),
                    granted_at = COALESCE(?, granted_at),
                    consumed_at = COALESCE(?, consumed_at)
                WHERE approval_id = ?;
                """,
                (state, reason, granted_at, consumed_at, approval_id),
            )

    def save_decision(self, decision: dict[str, Any]) -> None:
        with self.connection() as conn:
            # Ensure task exists to satisfy foreign key integrity
            now_t = time.time()
            conn.execute(
                "INSERT OR IGNORE INTO tasks (id, goal, state, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?);",
                (decision["task_id"], "Task stub", "CREATED", now_t, now_t, "{}"),
            )
            payload = json.dumps(decision.get("payload") or {})
            conn.execute(
                """
                INSERT INTO decisions (
                    decision_id, task_id, observation_id, action, target_description,
                    risk_level, confidence, requires_confirmation, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    risk_level=excluded.risk_level,
                    confidence=excluded.confidence,
                    payload=excluded.payload;
                """,
                (
                    decision["decision_id"],
                    decision["task_id"],
                    decision.get("observation_id", ""),
                    decision["action"],
                    decision.get("target_description", ""),
                    decision.get("risk_level", ""),
                    decision.get("confidence", ""),
                    1 if decision.get("requires_confirmation") else 0,
                    decision.get("created_at", time.time()),
                    payload,
                ),
            )

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM decisions WHERE decision_id = ?;", (decision_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["payload"] = json.loads(d.get("payload") or "{}")
            return d

    def list_decisions_for_task(self, task_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM decisions WHERE task_id = ? ORDER BY created_at ASC;",
                (task_id,),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d.get("payload") or "{}")
                results.append(d)
            return results

    # -----------------------------------------------------------------------
    # Phase 8: Workflow and Workflow Node CRUD Operations
    # -----------------------------------------------------------------------

    def create_workflow(self, workflow_data: dict[str, Any]) -> None:
        """Insert a new workflow record."""
        with self.connection() as conn:
            now_t = time.time()
            budget = workflow_data.get("resource_budget") or {}
            meta = workflow_data.get("metadata") or {}
            conn.execute(
                """
                INSERT INTO workflows (
                    workflow_id, task_id, goal, status, execution_generation,
                    resource_budget, deadline, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    workflow_data["workflow_id"],
                    workflow_data["task_id"],
                    workflow_data["goal"],
                    workflow_data.get("status", "CREATED"),
                    workflow_data.get("execution_generation", 1),
                    json.dumps(budget) if isinstance(budget, dict) else str(budget),
                    workflow_data.get("deadline"),
                    workflow_data.get("created_at", now_t),
                    workflow_data.get("updated_at", now_t),
                    json.dumps(meta) if isinstance(meta, dict) else str(meta),
                ),
            )

    def update_workflow(self, workflow_id: str, **kwargs) -> bool:
        """Update fields of an existing workflow record."""
        with self.connection() as conn:
            fields = []
            values = []
            kwargs["updated_at"] = time.time()
            for k, v in kwargs.items():
                if k not in ALLOWED_WORKFLOW_COLUMNS:
                    continue
                if k in ("resource_budget", "metadata") and isinstance(v, dict):
                    v = json.dumps(v)
                fields.append(f"{k} = ?")
                values.append(v)
            if not fields:
                return False
            values.append(workflow_id)
            query = f"UPDATE workflows SET {', '.join(fields)} WHERE workflow_id = ?;"  # nosec B608
            cursor = conn.execute(query, values)
            return cursor.rowcount > 0

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Retrieve a workflow by its workflow_id."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?;", (workflow_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            w = dict(row)
            w["resource_budget"] = json.loads(w.get("resource_budget") or "{}")
            w["metadata"] = json.loads(w.get("metadata") or "{}")
            return w

    def list_workflows(
        self, limit: int = 50, status: str | None = None
    ) -> list[dict[str, Any]]:
        """List workflows, optionally filtering by status."""
        with self.connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM workflows WHERE status = ? ORDER BY created_at DESC LIMIT ?;",
                    (status, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM workflows ORDER BY created_at DESC LIMIT ?;",
                    (limit,),
                )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                w = dict(r)
                w["resource_budget"] = json.loads(w.get("resource_budget") or "{}")
                w["metadata"] = json.loads(w.get("metadata") or "{}")
                results.append(w)
            return results

    def upsert_workflow_node(self, node_data: dict[str, Any]) -> None:
        """Insert or update a workflow node."""
        with self.connection() as conn:
            now_t = time.time()
            deps = node_data.get("dependencies") or []
            meta = node_data.get("metadata") or {}
            conn.execute(
                """
                INSERT INTO workflow_nodes (
                    node_id, workflow_id, goal, status, dependencies,
                    attempt_count, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id, workflow_id) DO UPDATE SET
                    status=excluded.status,
                    attempt_count=excluded.attempt_count,
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata;
                """,
                (
                    node_data["node_id"],
                    node_data["workflow_id"],
                    node_data["goal"],
                    node_data.get("status", "PENDING"),
                    json.dumps(deps) if isinstance(deps, list) else str(deps),
                    node_data.get("attempt_count", 0),
                    node_data.get("created_at", now_t),
                    node_data.get("updated_at", now_t),
                    json.dumps(meta) if isinstance(meta, dict) else str(meta),
                ),
            )

    def get_workflow_node(
        self, workflow_id: str, node_id: str
    ) -> dict[str, Any] | None:
        """Retrieve a node by workflow_id and node_id."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM workflow_nodes WHERE workflow_id = ? AND node_id = ?;",
                (workflow_id, node_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            n = dict(row)
            n["dependencies"] = json.loads(n.get("dependencies") or "[]")
            n["metadata"] = json.loads(n.get("metadata") or "{}")
            return n

    def list_workflow_nodes(self, workflow_id: str) -> list[dict[str, Any]]:
        """List all nodes for a workflow."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM workflow_nodes WHERE workflow_id = ? ORDER BY created_at ASC;",
                (workflow_id,),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                n = dict(r)
                n["dependencies"] = json.loads(n.get("dependencies") or "[]")
                n["metadata"] = json.loads(n.get("metadata") or "{}")
                results.append(n)
            return results

    def update_workflow_node(self, workflow_id: str, node_id: str, **kwargs) -> bool:
        """Update fields on an existing workflow node."""
        with self.connection() as conn:
            fields = []
            values = []
            kwargs["updated_at"] = time.time()
            for k, v in kwargs.items():
                if k not in ALLOWED_WORKFLOW_NODE_COLUMNS:
                    continue
                if k == "metadata" and isinstance(v, dict) or k == "dependencies" and isinstance(v, list):
                    v = json.dumps(v)
                fields.append(f"{k} = ?")
                values.append(v)
            if not fields:
                return False
            values.extend([workflow_id, node_id])
            query = f"UPDATE workflow_nodes SET {', '.join(fields)} WHERE workflow_id = ? AND node_id = ?;"  # nosec B608
            cursor = conn.execute(query, values)
            return cursor.rowcount > 0

    # -----------------------------------------------------------------------
    # Phase 9: Reliability & Self-Repair CRUD
    # -----------------------------------------------------------------------
    def create_incident(self, incident_data: dict[str, Any]) -> None:
        with self.connection() as conn:
            now_t = time.time()
            meta = incident_data.get("metadata") or {}
            conn.execute(
                """
                INSERT INTO incidents (
                    incident_id, workflow_id, node_id, severity, status,
                    description, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    incident_data["incident_id"],
                    incident_data.get("workflow_id"),
                    incident_data.get("node_id"),
                    incident_data.get("severity", "ERROR"),
                    incident_data.get("status", "OPEN"),
                    incident_data.get("description", ""),
                    now_t,
                    now_t,
                    json.dumps(meta),
                ),
            )

    def log_incident_event(
        self, incident_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO incident_events (incident_id, event_type, payload, timestamp) VALUES (?, ?, ?, ?);",
                (incident_id, event_type, json.dumps(payload), time.time()),
            )

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM incidents WHERE incident_id = ?;", (incident_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            i = dict(row)
            i["metadata"] = json.loads(i.get("metadata") or "{}")
            return i

    def list_incidents(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM incidents WHERE status = ? ORDER BY created_at DESC;",
                    (status,),
                )
            else:
                cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC;")
            return [dict(r) for r in cursor.fetchall()]


db = DatabaseManager()
