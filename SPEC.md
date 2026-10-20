# SPEC: COMPASS Phase 9 - Reliability & Self-Repair

## Overview
Phase 9 wraps the Phase 1-8 architecture in a diagnostic reliability shell. It introduces state reconciliation, immutable incident logging, and constrained autonomous self-repair—ensuring the system can diagnose and repair non-critical faults while enforcing strict cryptographic boundaries and human approval for consequential repairs.

## Architecture & Integration Points
Based on the `PHASE_9_REPOSITORY_AUDIT.md` and `PHASE_9_STATE_AUTHORITY.md`:

1. **Database Persistence**: SQLite WAL tables for `incidents`, `incident_events`, and `repair_plans`.
2. **State Authority**: 
   - Safety (Generation Fence) -> Database -> Checkpoints -> In-Memory
3. **Cryptographic Integrity**:
   - `verify_critical_integrity()` runs SHA-256 against a defined manifest. If a core system file is tampered with, the system goes into `CRITICAL_INTEGRITY_VIOLATION`, halting all self-repair and workflow execution.
4. **Diagnostic Engine**: Monitors execution timeouts, checkpoint corruptions, and UI assertion failures, logging them to the DB.
5. **Reliability APIs**: 
   - `GET /api/reliability/health`: System health aggregation.
   - `GET /api/reliability/events`: Real-time SSE stream of incident events.

## Endpoints
### `GET /api/reliability/health`
- **Output**: JSON payload representing `SystemHealthMonitor` status (HEALTHY, DEGRADED, UNHEALTHY, CRITICAL, STOPPED).
- **Errors**: 500 if database unreachable.

### `GET /api/reliability/events`
- **Output**: text/event-stream containing serialized `IncidentEvent` JSON payloads.

## Security & Safety
- **Strict Hierarchy**: Self-repair logic cannot override Phase 4 Safety or Phase 6 Checkpoint Authority.
- **Manifest Validation**: Tampering with `planner/workflow/orchestrator.py`, `planner/approval.py` etc., permanently locks the system into safe mode.
- **Human in the Loop**: Any repair plan that mutates existing source code requires explicit human approval via the Phase 4 Approval engine.
