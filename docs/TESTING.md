# COMPASS — Testing & Verification Guide

## 1. Test Architecture Overview

COMPASS testing operates across multiple distinct tiers:
1. **Unit & Component Tests (`pytest`):** In-memory and mocked verification of parsing, state machines, schemas, and security guards.
2. **Integration & API Tests:** Live endpoint testing using `starlette.testclient.TestClient` and HTTP requests against running FastAPI instances.
3. **Real Product E2E Suite (`assurance/real_product_suite.py`):** Assembled stack testing exercising live backend, Vite frontend, and controlled Windows UI applications.
4. **Adversarial & Fuzzing Suite:** Threat injection covering SQL injection, path traversal, prompt injection, and huge buffers.
5. **Continuous Assurance Runner (`assurance/compass_assure.py`):** 14-stage automated pipeline orchestrating all scanners, tests, and certification gates.

---

## 2. Test Harness Safety Rules

> [!IMPORTANT]
> The real-product QA harness (`assurance/real_product_harness.py`) enforces strict desktop safety rules:
> 1. **Owned Process Tracking:** The harness strictly terminates child processes that it spawned and tracks by PID. It never kills processes by name (e.g. `notepad.exe`).
> 2. **Port Protection:** Ports 8000 and 5173 are validated; foreign listeners cause a safe port conflict and fail closed rather than terminating unknown processes.
> 3. **Test Mode Isolation:** Adversarial tests require `COMPASS_TEST_MODE=1` verified in backend telemetry before executing to prevent live OS actions.
> 4. **Mock Application Labeling:** Tests utilizing `assurance/notepad.exe` are explicitly categorized as Mock WinForms tests, distinguished from native Windows application workflows.

---

## 3. Verified Execution Commands

### Run Unit and Regression Test Suites
```bash
# Full pytest regression suite
.venv\Scripts\pytest.exe -v

# Core planner & verification regression tests
.venv\Scripts\pytest.exe planner\tests\test_final_goal_regressions.py planner\tests\test_final_state_verification.py -v

# Plan validator exhaustive checks
.venv\Scripts\pytest.exe planner\tests\test_plan_validator_exhaustive.py -v

# Safety & coordinate tests
.venv\Scripts\pytest.exe automation\tests\test_coordinate_safety.py planner\tests\test_stale_guard.py -v

# Security trust boundary tests
.venv\Scripts\pytest.exe backend\tests\test_origin_boundary.py -v
```

### Run Assurance & Release Gate Suites
```bash
# Execute master assurance runner
.venv\Scripts\python.exe assurance/compass_assure.py --quick

# Run real product assembled test suite
.venv\Scripts\python.exe assurance/real_product_suite.py

# Run secret scanner
.venv\Scripts\python.exe assurance/tools/secret_scanner.py

# Run dependency security scanner
.venv\Scripts\python.exe assurance/tools/dependency_scanner.py
```
