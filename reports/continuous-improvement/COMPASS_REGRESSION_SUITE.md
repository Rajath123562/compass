# COMPASS Continuous Regression Testing Suite

**Document ID:** COMPASS-REGR-2026-006  
**Target Release:** COMPASS v2.0.0-verified.freeze  
**Coverage:** 808 Automated Unit / Integration Tests + 18 Real Product Tests + 20 Empirical Pilot Scenarios  
**Date:** 2026-10-18  

---

## 1. Regression Framework Architecture

To prevent regressions across development cycles, COMPASS maintains a multi-layered regression testing harness:

```
+-----------------------------------------------------------------------------------+
|                        COMPASS Continuous Regression Harness                       |
+-----------------------------------------------------------------------------------+
| Tier 1: Real-World Pilot Evaluation (20 Scenarios)                                |
|   - Basic Desktop Actions (B01 - B09)                                             |
|   - Multistep Workflows (M01 - M04)                                               |
|   - Edge Cases & Defensive Invariants (E01 - E07)                                 |
+-----------------------------------------------------------------------------------+
| Tier 2: Real Product Assurance Suite (18 Tests across 5 Suites)                   |
|   - Notepad E2E Automation & Verification (Suite 1)                               |
|   - Emergency Abort Latency < 200ms (Suite 2)                                     |
|   - Crash Resilience & Process Recovery (Suite 3)                                 |
|   - Adversarial Fuzzing & Malformed Payloads (Suite 4)                            |
|   - Memory RSS Leakage Stability (Suite 5)                                        |
+-----------------------------------------------------------------------------------+
| Tier 3: Core Multi-Phase Pytest Test Suite (808 Tests)                            |
|   - Security, Threat Mitigation, and Sanitization (Phases 5-6, 13)                |
|   - Workflow DAG, Concurrency, and Loop Detection                                 |
|   - Verification Engine, Goal Postcondition Assertions                            |
|   - StaleGuard, Target Resolver, and Action Dispatcher                            |
|   - Assurance Gates, Finding Registry, and Secret Scanners                        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Test Execution Commands & Repeatability Guide

All tests can be executed locally in a standard Windows PowerShell environment using the commands below:

### 2.1 Running the 20-Scenario Realistic Pilot Evaluation
```powershell
# Executes the 20-scenario empirical pilot suite against live Windows desktop apps
python scripts/run_realistic_pilot_evaluation.py
```
- **Output Artifact:** [reports/continuous-improvement/pilot_evaluation_results.json](file:///c:/Users/RAJATH%20U/Downloads/personal%20assitant/reports/continuous-improvement/pilot_evaluation_results.json)
- **Expected Result:** `20 PASSED, 0 FAILED, 0 FALSE SUCCESSES`

### 2.2 Running the Real Product Assurance Suite
```powershell
# Executes end-to-end real product verification with MockNotepad and external observer
python assurance/real_product_suite.py
```
- **Expected Result:** `All 18 tests passed across 5 suites`

### 2.3 Running the Core Multi-Phase Regression Suite
```powershell
# Executes all 808 unit and integration tests across planner, backend, and assurance
python -m pytest -q --tb=short
```
- **Expected Result:** `808 passed`

### 2.4 Running Targeted Defect Regressions
```powershell
# Specifically verifies DEF-009, DEF-010, and related defect remediations
python -m pytest planner/tests/test_phase11_defects.py -v
python -m pytest planner/tests/test_final_goal_regressions.py -v
```
- **Expected Result:** Clean pass across all defect regression assertions.

---

## 3. Module Coverage & Invariant Mapping

| Module / Subsystem | Primary Test Files | Invariants Enforced |
| :--- | :--- | :--- |
| **Input Schema & Models** | `backend/tests/`, `test_phase11_defects.py` | Rejection of whitespace-only / blank goals (DEF-009) |
| **AI Safety Governor** | `planner/tests/test_circuit_breaker.py` | State transitions (CLOSED, OPEN, HALF_OPEN) & timeout isolation |
| **Goal Verification** | `planner/tests/test_final_goal_regressions.py` | Fail-closed on missing/throwing verifier (AUDIT-001/002) |
| **Observation Safety** | `planner/tests/test_final_goal_regressions.py` | OBSERVE action is strictly non-mutating (AUDIT-003) |
| **Workflow DAG Engine** | `planner/tests/test_workflow_*.py` | Cycle detection, topological sort, concurrency isolation |
| **StaleGuard** | `planner/tests/test_stale_guard.py` | Cache invalidation on elapsed time (>5s) or target drift |
| **Process Cleanup** | `planner/tests/test_cleanup.py` | Guaranteed cleanup on task success, abort, or failure |
