# TASKS: COMPASS Phase 9 - Reliability
Status key: [ ] todo, [~] in progress, [x] done

## Risks and handling
| Risk | Likelihood | How handled |
|------|-----------|-------------|
| Checkpoint Reconciliation loops | High | Generation ID fencing ensures stale orchestration loops cannot fight DB authority. |
| Unauthorized Self-Repair | Medium | SHA-256 Integrity Manifest blocks self-repair if core files mismatch. |
| Test Regression | High | 100% pass rate requirement across all existing Phase 1-8 tests plus new Phase 9 tests. |

## Tasks

### T1: Database Schema & Health API
- [x] Status
- Files: `backend/app/models.py`, `backend/app/routers/reliability.py`, `backend/app/main.py`
- Do: Add SQLAlchemy models for `incidents`, `incident_events`, `repair_plans`. Implement `GET /api/reliability/health` mapping to system states. 
- Done when: Database tables are initialized and health endpoint returns 200 HEALTHY.
- Test: `pytest backend/tests/test_reliability_api.py`

### T2: Cryptographic Integrity Manifest
- [x] Status
- Depends on: T1
- Files: `planner/reliability/integrity.py`, `planner/tests/test_integrity.py`
- Do: Implement `verify_critical_integrity(manifest: dict)` using `hashlib.sha256`. 
- Done when: Corrupted files trigger a `CRITICAL_INTEGRITY_VIOLATION` boolean flag preventing orchestration.
- Test: `pytest planner/tests/test_integrity.py`

### T3: Incident Logger & Execution Hook
- [x] Status
- Depends on: T2
- Files: `planner/reliability/diagnostics.py`, `planner/workflow/orchestrator.py`
- Do: Hook into `WorkflowOrchestrator` execution loops. On unhandled `Exception` or `CheckpointCorruptedError`, emit a structured `Incident` to the DB instead of crashing.
- Done when: Workflows gracefully fail nodes, emit incident rows, and don't take down the background loop.
- Test: `pytest planner/tests/test_diagnostics.py`

### T4: Self-Repair Guard & SSE Events
- [x] Status
- Depends on: T3
- Files: `planner/reliability/repair.py`, `backend/app/routers/reliability.py`
- Do: Implement human-approval gating for `repair_plans`. Wire `GET /api/reliability/events` SSE endpoint to broadcast incidents via `asyncio.Queue`.
- Done when: Connecting an HTTP client to the SSE endpoint streams live incidents emitted by T3 hooks.
- Test: `pytest backend/tests/test_reliability_sse.py`

### T5: Master Phase 9 Validation
- [x] Status
- Depends on: T4
- Files: `scripts/run_phase9_tests.py`
- Do: Create the Phase 9 test runner that validates zero regression on `planner/tests/` and executes the new reliability suites.
- Done when: Entire suite passes with 0 failures.
- Test: `python scripts/run_phase9_tests.py`
