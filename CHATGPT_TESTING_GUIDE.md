# COMPASS — Complete Project Guide & Test Protocol for ChatGPT

Welcome, ChatGPT! This project is **COMPASS (Context-Oriented Multimodal Personal Assistant with Safety & Supervision)**.
This package has been optimized to extract and run cleanly in the ChatGPT sandbox without exceeding file size, memory, or execution limits.

---

## 🚀 1. Quick Start: Test Everything in 1 Command

Run the automated test runner inside your Code Interpreter environment:

```bash
python chatgpt_run_all_tests.py
```

This script will automatically:
1. **Verify Database Integrity**: Connect to `storage/compass.db`, verify all 12 tables, and run `PRAGMA integrity_check`.
2. **Verify Core Module Architecture**: Check imports for FastAPI backend, DAG workflow engine, safety guards, and providers.
3. **Verify In-Memory DAG Execution**: Create a Directed Acyclic Graph, test dependency resolution, acyclicity validation, and topological sorting.
4. **Verify Consequential Safety Rules**: Validate that destructive actions (e.g., delete) trigger HIGH risk and require human confirmation, while observational actions are LOW risk.
5. **Run the Pytest Suite**: Execute the full unit and integration test suite across all modules.

---

## 🧪 2. Running Pytest Directly

You can also run pytest per subsystem or across the whole suite:

```bash
# Run the entire test suite
pytest -q --tb=short

# Run specific subsystem tests
pytest backend/tests/        # FastAPI routes, models, config, database
pytest planner/tests/        # DAG engine, circuit breaker, safety guards
pytest assurance/tests/      # Security auditor, release gates, secret scanner
pytest providers/tests/      # AI providers, token counting, fallbacks
pytest overlay/tests/        # Overlay controller, visual state, launcher
pytest perception/tests/     # Screen capture, OCR engine, window locator
pytest automation/tests/     # Action dispatcher, target resolver, input drivers
```

*Note: Cross-platform mock stubs are provided in `conftest.py` so Windows-specific packages (`comtypes`, `winrt`, `PySide6`) are gracefully mocked when running in Linux/ChatGPT.*

---

## 📁 3. Architecture & Codebase Map

| Subsystem | Location | Description |
| :--- | :--- | :--- |
| **Backend** | `backend/app/` | FastAPI REST API, SQLite database models, logging, settings |
| **Planner** | `planner/` | Dynamic DAG task decomposition, loop detection, circuit breakers, risk classifier, recovery WAL checkpoints |
| **Automation** | `automation/` | OS input simulation, Windows UI Automation (UIA), element locator, action dispatcher |
| **Perception** | `perception/` | Real-time screen capture, OCR pipeline, window tracking, text bounding boxes |
| **Providers** | `providers/` | Multi-LLM provider abstraction (Gemini, Claude, OpenAI, Local/Mock), token budgets |
| **Overlay** | `overlay/` | HUD, floating prompt bar, risk banners, feedback indicators |
| **Assurance** | `assurance/` | Production test harness, vulnerability scanner, audit reports, release gates |
| **Storage** | `storage/` | SQLite database (`compass.db`) with active schemas and audit history |
| **Frontend** | `frontend/` | React/Vite web application dashboard and control interface |
| **Docs** | `docs/` | Architecture specs, threat models, API references, phase audit documentation |

---


stic Risk Gating**: Any destructive action (`delete`, `terminate`, `rm`, `drop`) is classified as `HIGH` risk and CANNOT proceed without human confirmation.
2. **AI Circuit Breaker**: If consecutive planning failures exceed threshold (3 failures), the circuit trips to `OPEN`, immediately blocking further automated actions until manual reset.
3. **Write-Ahead Log (WAL) Checkpoints**: Every task state transition is persisted with HMAC integrity verification.
4. **Secret Scrubbing**: All bearer tokens, API keys, and sensitive credentials in traces, logs, and checkpoints are redacted with `[REDACTED]`.

---

## 💻 5. Frontend Inspection

The web frontend is located in `frontend/`:
- `frontend/src/`: React UI components, dashboard, action feed, and controls.
- `frontend/package.json`: Dependency manifests and scripts.
- To inspect or validate the frontend build:
  ```bash
  cd frontend && npm test # or inspect package.json
  ```
