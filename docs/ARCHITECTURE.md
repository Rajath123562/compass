# Architecture

## Core Flow
1. **Goal Input** -> Target Resolution (Heuristics + AI)
2. **Context Builder** -> Parses current state from `perception/`
3. **Planning** -> AI model creates TaskPlan.
4. **Execution** -> Sent via DAG workflow to `automation/`.
5. **Verification** -> 6-point live tree check.

## Data Flow
- In-memory checks backed up by SQLite WAL (`compass.db`).
