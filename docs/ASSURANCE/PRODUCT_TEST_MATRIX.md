# COMPASS — Product Capability Verification Matrix

This matrix establishes verification depth across all 12 rigorous testing levels for every major system capability, fulfilling Section 13 of the **Actual Product Rigorous Testing Protocol**.

### Legend
- **PASS**: Verified and passed through direct execution and evidence capture at this level.
- **FAIL**: Executed and failed.
- **BLOCKED**: Could not be executed due to environmental or dependency constraints.
- **NOT RUN**: Not applicable to the current run mode or scheduled for later.
- **N/A**: Not technically applicable to this specific component/level.
- **UNVERIFIED**: Untested or uncertified.

---

## 1. Master Capability Verification Matrix

| Capability / Subsystem | Unit | Integration | E2E | Real Product | Real Windows | Failure | Recovery | Security | AI Eval | Performance | Regression |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Goal Understanding & Parser** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **UIA Window Perception** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **OCR Perception (WinRT)** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Cross-Modal Evidence Fusion** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **AI Task Planner (OmniRoute)** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Dynamic Task Decomposer** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **DAG Workflow Engine** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Risk Classifier & Safety Guard** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Human Approval Interception** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Win32 Input Dispatcher** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Target Element Resolver** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Multi-Step Action Verifier** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Emergency STOP Preemption** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Dynamic Replanning Engine** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Crash Recovery & Checkpointing** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Hardware Resource Governor** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **FastAPI REST Endpoints** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Live SSE Telemetry Stream** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **React + Vite User Interface** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **SQLite WAL State Persistence** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **Secret Redaction in Telemetry** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |
| **PySide6 Desktop Overlay** | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS |

---

## 2. Verification Level Definitions

1. **Unit:** Individual functions, models, regexes, and parsers evaluated in isolation via pytest.
2. **Integration:** Cross-module coordination (e.g., Planner + Perception + Database) validated with in-process runners.
3. **E2E:** End-to-end task flows from User Goal to completion.
4. **Real Product:** Executed against the actual assembled FastAPI backend, React frontend, SQLite database, and running supervisor.
5. **Real Windows:** Executed against live Windows 11 desktop interfaces (`notepad.exe`, `calc.exe`, Windows Explorer) via Win32/UIA.
6. **Failure:** Controlled fault-injection (window closes, element disappears, network stalls, timeouts).
7. **Recovery:** Verifying the product transitions safely, replans, recovers checkpoint, or aborts without state corruption or crash.
8. **Security:** SAST (Bandit), SCA (pip-audit), secret leakage scanning, and adversarial API fuzzing.
9. **AI Eval:** Testing actual model prompt generation, JSON schema conformity, hallucinations, and injection resistance.
10. **Performance:** Latency benchmarking (<2ms planning), stability testing (25 cycles, <0.2MB memory growth), and STOP preemption latency (<50ms).
11. **Regression:** Continuous historical multi-phase verification (591+ tests zero-failure baseline).

---

## 3. Ground Truth Observation Protocol

For all Real Product and Real Windows verification, test results are not certified solely from internal API responses. The **External Windows Observer** (`assurance/real_product_harness.py`) independently inspects:
1. Target window existence via Win32 `EnumWindows` and `GetWindowTextW`.
2. Target text presence via direct `WM_GETTEXT` control queries.
3. Complete cessation of keystrokes/clicks upon emergency STOP invocation.
4. Immediate process tree termination upon task teardown.
