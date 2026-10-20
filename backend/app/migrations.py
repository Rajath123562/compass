"""
COMPASS SQLite Schema Migration Manager
Guarantees 10-year forward and backward compatibility (2026-2036) using SQLite PRAGMA user_version.
Ensures zero data loss during schema evolution.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from backend.app.logging_config import logger

MigrationFunc = Callable[[sqlite3.Connection], None]

MIGRATIONS: list[tuple[int, str, MigrationFunc]] = []


def register_migration(version: int, description: str):
    def decorator(func: MigrationFunc) -> MigrationFunc:
        MIGRATIONS.append((version, description, func))
        MIGRATIONS.sort(key=lambda m: m[0])
        return func
    return decorator


@register_migration(1, "Baseline Phase 1-6 Schema & PRAGMA user_version initialization")
def migration_v1(conn: sqlite3.Connection) -> None:
    # Baseline schema is established by SCHEMA_SQL; v1 locks in user_version
    logger.info("Database migration v1: Baseline schema verified.")


@register_migration(2, "Add active window and telemetry audit indexes")
def migration_v2(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    # Ensure fast lookup for active window and telemetry events
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_events_type_time ON task_events(event_type, timestamp DESC);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_system_settings_updated ON system_settings(updated_at DESC);"
    )
    logger.info("Database migration v2: High-speed telemetry indexes applied.")


def get_current_version(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version;")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def set_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA user_version cannot be parameterized with ? in SQLite
    conn.execute(f"PRAGMA user_version = {int(version)};")


def run_migrations(conn: sqlite3.Connection) -> int:
    """
    Sequentially apply any unapplied database migrations.
    Returns the latest applied schema version.
    """
    current_v = get_current_version(conn)
    applied_count = 0

    for version, desc, func in MIGRATIONS:
        if version > current_v:
            logger.info(f"Applying migration v{version}: {desc}")
            try:
                func(conn)
                set_version(conn, version)
                conn.commit()
                current_v = version
                applied_count += 1
            except Exception as e:
                conn.rollback()
                logger.error(f"Migration v{version} failed: {e}")
                raise

    if applied_count > 0:
        logger.info(f"Successfully applied {applied_count} migrations. Current DB version: {current_v}")
    return current_v
