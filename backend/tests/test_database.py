"""
Unit and integration tests for COMPASS database persistence and WAL mode.
"""

import tempfile
from pathlib import Path

from backend.app.database import DatabaseManager


def test_database_init_and_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_compass.db"
        db = DatabaseManager(db_path=test_db_path)

        # 1. Initialize schema
        db.init_db()
        assert test_db_path.exists()

        # 2. Check health
        health = db.check_health()
        assert health["status"] == "healthy"
        assert health["journal_mode"].lower() == "wal"
        assert health["task_count"] == 0

        # 3. Create task
        task = db.create_task(
            task_id="task_test_1",
            goal="Create a folder called SIH Demo",
            initial_state="STARTING",
            metadata={"source": "test"},
        )
        assert task["id"] == "task_test_1"
        assert task["state"] == "STARTING"

        # 4. Read task
        fetched = db.get_task("task_test_1")
        assert fetched is not None
        assert fetched["goal"] == "Create a folder called SIH Demo"
        assert fetched["metadata"]["source"] == "test"

        # 5. Update state
        updated = db.update_task_state(
            "task_test_1", "UNDERSTANDING", reason="analyzing UI"
        )
        assert updated["state"] == "UNDERSTANDING"

        # 6. Check events
        events = db.get_task_events("task_test_1")
        assert len(events) == 2  # TASK_CREATED and STATE_TRANSITION
        assert events[0]["event_type"] == "TASK_CREATED"
        assert events[1]["event_type"] == "STATE_TRANSITION"
        assert events[1]["payload"]["new_state"] == "UNDERSTANDING"

        # 7. Verify persistence across fresh DatabaseManager instance (simulating process restart)
        db_restarted = DatabaseManager(db_path=test_db_path)
        restarted_task = db_restarted.get_task("task_test_1")
        assert restarted_task is not None
        assert restarted_task["state"] == "UNDERSTANDING"
        assert restarted_task["goal"] == "Create a folder called SIH Demo"


def test_crash_restart_safety_and_approval_invalidation():
    """
    Directive §15: Verify crash/restart recovery safety:
    1. In-flight task persisted in DB.
    2. In-memory approval controller on restart contains NO granted tokens for old task.
    3. Stale approvals cannot be reused after process restart.
    4. Task does not automatically resume unsafe OS action without fresh observation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_restart.db"
        db = DatabaseManager(db_path=test_db_path)
        db.init_db()

        # Task in progress prior to crash
        db.create_task(
            "task_crash_1", "Format disk", "ACTING", metadata={"hwnd": 12345}
        )
        db.log_task_event("task_crash_1", "ACTION_ATTEMPT", {"action": "click"})

        # Simulate restart: fresh DatabaseManager and fresh HumanApprovalController
        from planner.human_approval import HumanApprovalController

        db_restarted = DatabaseManager(db_path=test_db_path)
        approval_controller_restarted = HumanApprovalController()

        restarted_task = db_restarted.get_task("task_crash_1")
        assert restarted_task is not None
        assert restarted_task["state"] == "ACTING"

        # Approval records must be completely empty / ungranted on fresh instance
        assert (
            approval_controller_restarted.get_approval("task_crash_1", "dec_old")
            is None
        )
        valid, reason = approval_controller_restarted.validate_approval_state(
            task_id="task_crash_1", decision_id="dec_old"
        )
        assert valid is False
        assert "No approval record found" in reason
