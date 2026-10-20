"""
Unit tests for SQLite Schema Migration Manager (10-year forward/backward durability).
"""

import sqlite3

from backend.app.database import SCHEMA_SQL
from backend.app.migrations import get_current_version, run_migrations


def test_migrations_fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    # Initial version before migrations is 0
    assert get_current_version(conn) == 0

    # Run migrations
    latest_v = run_migrations(conn)
    assert latest_v >= 2
    assert get_current_version(conn) == latest_v

    # Verify migration v2 created the index
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_task_events_type_time';")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "idx_task_events_type_time"

    conn.close()


def test_migrations_idempotency():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    v1 = run_migrations(conn)
    v2 = run_migrations(conn)
    assert v1 == v2
    assert get_current_version(conn) == v2

    conn.close()
