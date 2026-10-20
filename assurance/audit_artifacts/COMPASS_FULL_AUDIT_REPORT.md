# COMPASS Full Engineering and Actual-Product Audit Report

**Audit conclusion: NOT READY FOR CERTIFICATION**  
**Scope:** Evidence-backed archive review, targeted source inspection, static checks, and host pytest execution.  
**Important limitation:** The uploaded ZIP was audited on Linux, not on the supported target Windows desktop. The actual assembled COMPASS application, real UIA/Win32, overlay, browser workflows, and live model-backed execution were not run in this audit. This report does not claim that every one of the counted source lines was manually reasoned through or that every possible defect has been found.

## 1. Executive summary

The archive contains a substantial COMPASS codebase and test/assurance infrastructure. It is not presently possible to certify that the assembled product is completely correct or working. There are evidence-backed defects in final-goal verification and action reporting, significant safety hazards in the current real-product harness, and defects in release-gate logic that can misreport failure as a passing stage. Stored historical certification artifacts contradict one another and do not establish a reproducible current certified source revision.

### Critical findings
- **2 CRITICAL finding(s)** in this audit register. Most urgent: the adversarial harness can submit a destructive instruction through an auto-executing task endpoint without establishing isolation/test mode; and the assurance master runner can label a release-gate stage PASS even when the release gate reports FAIL.
- False-success paths exist where the final task can be marked completed without sufficient independent final-goal evidence.
- Product test assertions accept backend liveness or broad HTTP status codes instead of verifying correct, safe real behavior.
- Running the current harness on a normal active desktop can terminate all `notepad.exe` processes and can kill unrelated listeners on ports 8000/5173.

### Test execution
- ZIP integrity: **PASS**.
- Python `compileall`: **PASS**, exit code 0 for selected Python source trees.
- Host full pytest: **FAIL**, 45 failed, 491 passed, 12 skipped, 5 warnings, 25 errors in 20.80s.
- Actual Windows/product E2E: **NOT RUN** in this audit environment.
- No source fixes were applied by this audit.

### Immediate recommendation
**Do not run `assurance/real_product_suite.py`, `assurance/real_product_harness.py`, or startup/cleanup paths that kill processes or ports against your active desktop until the identified process-isolation and auto-execution hazards are fixed and independently tested.** The adversarial test contains a destructive prompt, while the harness may auto-execute task creation. Use an isolated disposable VM/user session and a fail-closed action adapter after correction.

## 2. Scope, method and confidence

This audit examined the supplied ZIP as a read-only copy. The ZIP SHA-256 is:

`ba99fc2439aabd8978b329a9bf2c171f5cfe5e6ba4fd357525343cfcd085ba6c`

Archive integrity test: `PASS`. Archive contains 1,954 entries and 7,208,596 uncompressed bytes. Selected source/script extension inventory counted 329 files and 61,156 lines, including 306 Python files. These are inventory counts, not a statement that every line has been manually understood.

Activities actually performed:
- inspected ZIP inventory and repository layout;
- reviewed key source paths for execution, verification, safety, test harness and release-gate behavior;
- reviewed existing documentation and stored assurance reports;
- ran Python compileall across selected source trees;
- ran full available pytest invocation in this Linux environment;
- captured reproducible test outputs and identified targeted behavioral mismatches;
- generated a structured findings register and remediation plan.

Not performed:
- native Windows execution;
- real UIA/Win32/overlay test;
- actual assembled frontend/backend desktop workflow in a supported Windows environment;
- model-backed live AI task run;
- live browser test against an installed Playwright browser;
- authorized penetration test against a running product;
- long-duration test on target hardware;
- verified clean build tied to a Git commit (archive lacks `.git`).

## 3. Environment and archive provenance

- Audit host: `Linux-6.18.44-x86_64-with-glibc2.41`
- Python: `3.13.5`
- Node: `v22.16.0`
- npm: `10.9.2`
- pytest: `pytest 9.0.2`
- `.git` metadata in archive: no
- `.venv` in archive: no
- `frontend/node_modules` in archive: no

Without Git metadata, this ZIP cannot establish which exact commit/tag existing certifications refer to. This is not proof the project was never version-controlled; it means source provenance is unavailable in this archive.

The ZIP includes `storage/compass.db` (~557 KB) and `logs/compass.log` (~449 KB). Those may contain task/activity data and should be inspected/redacted before sharing publicly. The audit bundle generated from this review does not copy the database or runtime log. The archive also contains a stray zero-byte file `6}`.

## 4. Actual tests run

| Test/check | Actual result | Interpretation |
|---|---|---|
| ZIP integrity | PASS | Container is readable; says nothing about application correctness. |
| Python compileall | PASS | Selected Python files compile; does not establish runtime or product correctness. |
| Full pytest on Linux | FAIL — 45 failed, 491 passed, 12 skipped, 5 warnings, 25 errors in 20.80s | Mixed platform/dependency failures and behavioral failures; target Windows rerun required. |
| Actual product startup | NOT RUN | Audit host is Linux and the product is Windows-dependent; harness hazards also make a live desktop run unsafe before fixes. |
| Real Windows UIA/Win32 | NOT RUN | Requires target Windows desktop. |
| Browser E2E with real browser | NOT RUN | Playwright browser runtime was not available in the environment. |
| Model-backed full loop | NOT RUN | No live AI provider/model execution was performed. |
| Live security testing | NOT RUN | Source/config review only; no exploitability claim without runtime validation. |

The 25 collection errors include tests that import Windows-specific code and hit `AttributeError: module 'ctypes' has no attribute 'WinDLL'` on Linux; other errors reference absent GUI/browser/property-testing dependencies. Some failed tests are platform-sensitive and need supported Windows execution. Other failures expose behavioral mismatches, such as coordinate bounds, stale HWND handling, and async runner behavior; target-platform confirmation is required where relevant.

Selected failures shown by the raw pytest output:
- `overlay/tests/test_hotkey_daemon.py::test_hotkey_daemon_lifecycle - assert False is True`
- `overlay/tests/test_overlay.py::test_overlay_window_properties - assert 1 == 0`
- `overlay/tests/test_overlay.py::test_overlay_subprocess_clean_exit - AssertionError: assert 1 == 0`
- `perception/tests/test_screen_capture.py::test_capture_desktop - AttributeError: module 'ctypes' has no attribute 'windll'`
- `perception/tests/test_screen_capture.py::test_capture_window_invalid_hwnd - AttributeError: module 'ctypes' has no attribute 'windll'`
- `perception/tests/test_screen_capture.py::test_capture_window_valid_hwnd - AttributeError: module 'ctypes' has no attribute 'windll'`
- `automation/tests/test_action_safety.py::TestHWNDSafe::test_regular_window_safe - AssertionError: assert False is True`
- `automation/tests/test_action_safety.py::TestHWNDSafe::test_taskbar_hwnd_rejected - AssertionError: assert 'protected' in 'not running on windows'`
- `automation/tests/test_action_safety.py::TestForegroundContext::test_matching_hwnd_passes - AttributeError: module 'ctypes' has no attribute 'windll'`
- `automation/tests/test_action_validator.py::TestActionValidatorUnit::test_click_valid_element - AssertionError: assert False is True`
- `automation/tests/test_action_validator.py::TestActionValidatorUnit::test_type_into_button_rejected - AssertionError: assert ('not editable' in 'not running on windows' or 'Edit' in 'Not running on Windows')`
- `automation/tests/test_action_validator.py::TestActionValidatorUnit::test_stale_element_rejected - AssertionError: assert 'revalidation' in 'not running on windows'`
- `automation/tests/test_browser_adapter.py::TestBrowserLifecycle::test_start_and_stop - assert False is True`
- `automation/tests/test_browser_adapter.py::TestBrowserLifecycle::test_navigate_and_get_text - AssertionError: assert False is True`
- `automation/tests/test_browser_adapter.py::TestBrowserLifecycle::test_screenshot - AssertionError: assert False is True`
- `automation/tests/test_coordinate_safety.py::test_coordinate_safety_reject_offscreen_impossible_coords - AssertionError: assert True is False`
- `planner/tests/test_ai_untrusted_validation.py::TestAIUntrustedValidationPipeline::test_gate_03_target_validation - AssertionError: assert ('not a valid window' in 'not running on windows' or 'missing' in 'not running on windows' or 'not found' in 'not running on windows')`
- `planner/tests/test_ai_untrusted_validation.py::TestAIUntrustedValidationPipeline::test_gate_04_parameter_validation - AssertionError: assert ('bounds' in 'negative coordinates (-500, 999999) are invalid.' or 'screen' in 'negative coordinates (-500, 999999) are invalid.')`
- `planner/tests/test_cancellation_everywhere.py::test_late_ai_response_neutralized_after_stop - AssertionError: assert 'FAILED' == 'STOPPED'`
- `planner/tests/test_cleanup.py::test_cleanup_after_ai_unavailable - assert 'circuit breaker is OPEN' in "module 'ctypes' has no attribute 'windll'"`
- `planner/tests/test_concurrency_deep.py::test_duplicate_execution_prevention - assert 0 == 1`
- `planner/tests/test_concurrency_deep.py::test_simultaneous_task_execution - assert False is True`
- `planner/tests/test_concurrency_deep.py::test_stop_vs_execution_race - AssertionError: assert 'FAILED' == 'STOPPED'`
- `planner/tests/test_concurrency_deep.py::test_approval_vs_stop_race - AssertionError: assert 'FAILED' == 'STOPPED'`
- `planner/tests/test_concurrency_deep.py::test_late_ai_response_after_cancellation - AssertionError: assert 'FAILED' == 'STOPPED'`
- `planner/tests/test_crash_recovery_phase5.py::test_target_window_closed_between_steps - AssertionError: assert True is False`
- `planner/tests/test_crash_recovery_phase5.py::test_planner_failure_fails_safely - assert 'OmniRoute upstream connection dropped' in "module 'ctypes' has no attribute 'windll'"`
- `planner/tests/test_diagnostics.py::test_orchestrator_emits_incident_on_failure - RuntimeError: Runner.run() cannot be called from a running event loop`
- `planner/tests/test_execution_engine.py::TestExecutionEngine::test_single_action_loop_success - assert False is True`
- `planner/tests/test_failures_extended.py::test_scenario_s_target_hwnd_destroyed_invalidation - AssertionError: assert True is False`
- `planner/tests/test_failures_extended.py::test_scenario_u_invalid_api_confirmation_rejection - AttributeError: module 'ctypes' has no attribute 'WinDLL'`
- `planner/tests/test_final_state_verification.py::test_action_success_does_not_equal_task_success_when_final_state_absent - AssertionError: assert 'FAILED' == 'BLOCKED'`
- `planner/tests/test_final_state_verification.py::test_action_success_with_verified_final_state_completes_task - assert False is True`
- `planner/tests/test_idempotency_recovery.py::test_non_repeatable_action_fails_verification_cannot_retry - AssertionError: assert 'FAILED' == 'BLOCKED'`
- `planner/tests/test_idempotency_recovery.py::test_non_repeatable_action_dispatch_failure_cannot_retry - assert 'Non-repeatable' in "module 'ctypes' has no attribute 'windll'"`
- `planner/tests/test_idempotency_recovery.py::test_repeatable_action_allows_bounded_retry - assert False is True`
- `planner/tests/test_phase11_defects.py::TestPhase11Defects::test_def_p11_01_circuit_breaker_open_transitions_to_ai_unavailable - assert None == 'AI_UNAVAILABLE'`
- `planner/tests/test_phase11_defects.py::TestPhase11Defects::test_def_p11_01_planning_ai_failure_transitions_safely - assert 'AI gateway offline' in "module 'ctypes' has no attribute 'windll'"`
- `planner/tests/test_phase12_functional_loop.py::TestPhase12FunctionalLoop::test_pre_dispatch_target_revalidation_rejects_closed_window - AssertionError: assert True is False`
- `planner/tests/test_phase13_adversarial.py::TestPhase13AdversarialHardening::test_ai_attack_out_of_bounds_negative_and_extreme_coordinates - AssertionError: assert True is False`
- `planner/tests/test_security_phase5.py::test_hallucinated_target_fails_revalidation - AttributeError: module 'ctypes' has no attribute 'windll'`
- `planner/tests/test_stale_guard.py::test_stale_guard_dead_hwnd_detected - AssertionError: assert True is False`
- `planner/tests/test_workflow_orchestrator.py::test_orchestrator_end_to_end - RuntimeError: Runner.run() cannot be called from a running event loop`
- `planner/tests/test_workflow_orchestrator.py::test_universal_stop - RuntimeError: Runner.run() cannot be called from a running event loop`
- `planner/tests/test_workflow_scheduler.py::test_lock_manager_ab_ba - RuntimeError: Runner.run() cannot be called from a running event loop`

Full raw logs: `evidence/logs/compileall.log` and `evidence/logs/pytest_full.log`.

## 5. High-level architecture reconstruction

The repository contains Python/FastAPI backend code, React/Vite frontend source, planner and execution engines, Windows automation/perception code, UI overlay code, persistence/event components, and an `assurance/` area with scanners, benchmark reports, findings registry, release gate and real-product tests.

The intended safety-critical trust path should be:

`untrusted goal/model/UI content → structured parse → schema validation → semantic plan validation → target and freshness validation → action/risk authorization → safety checks and required approval → controlled single action → independent observation → goal-specific final-state verification`

The implementation has paths that short-circuit this chain: completed intermediate steps can be treated as successful final goal completion, action launch can report success after an exception, and product-level test assertions do not consistently prove the intended outcome.

The repo also contains parallel workflow implementations. The runtime API imports top-level `planner.workflow_models` / `planner.workflow_orchestrator`; some tests import `planner.workflow.*`. This can leave production-path behavior under-tested.

## 6. Phase 1–14 assessment

The names below are an audit mapping based on available repository artifacts and project context. They are not new certification claims. Historical records are contradictory; none of these phases should be treated as currently recertified solely from this ZIP.

| Phase | Scope | Evidence-based assessment | Main concern | Current audit status |
|---:|---|---|---|---|
| 1 | Platform foundation | Windows/runtime baseline, backend/frontend scaffold, SQLite and overlay foundation. | Source/artifacts/tests present; compileall passes. ZIP cannot prove original environment or historical run. | Historical tag/commit unavailable; target Windows not tested. | NOT CURRENTLY CERTIFIED |
| 2 | Windows perception/action | UIA, Win32, GDI capture, semantic targeting and dispatch. | Windows-specific imports cause collection errors on Linux; real UIA/Win32 not run. | Coordinate and stale-guard issues observed; supported Windows rerun needed. | NOT CURRENTLY CERTIFIED |
| 3 | AI planner/OmniRoute | Planner, routing, structured response and decision engine. | Relevant source exists; actual AI/provider runtime not exercised. | Model/provider and real task execution absent from audit host. | UNVERIFIED |
| 4 | Live acceptance | Integration/acceptance validation. | Acceptance scripts/evidence exist; current suite still has failures; live acceptance not run. | Historical evidence does not map to an identified commit. | UNVERIFIED |
| 5 | Reliability hardening | Target validation, safety checks, result/verification handling. | Tests exist; final verifier/action verifier weaknesses found. | False-success paths need correction and regression coverage. | FAIL — HIGH-RISK FINDINGS |
| 6 | Multi-step workflows | Task steps/orchestration, checkpoints, SSE and recovery. | Source/tests exist; workflow tests include async errors; dual orchestrator implementations. | Runtime import path may not be the one unit tests exercise. | PARTIALLY VERIFIED |
| 7 | Advanced perception | Visual/UIA perception evolution. | Source and scripts exist; dependencies/runtime unavailable on Linux. | Real Windows/visual/OCR tests blocked. | UNVERIFIED |
| 8 | Universal app/browser workflows | Cross-app/browser actions and real Windows tests. | Scripts exist; Playwright browser runtime unavailable and live Windows not run. | Cannot claim cross-app capability from code-only review. | UNVERIFIED |
| 9 | Specification/documentation | Historical records suggest a docs-only phase in some prior context. | Current archive has docs and artifacts, but contradictory phase/certification records. | Need authoritative history/source tree to establish phase boundary. | DOCUMENTATION CLAIM; CODE COMPLETION NOT PROVEN |
| 10 | Integration/assurance hardening | Reliability, stability and system-level integration. | Historical reports/scripts exist; tests fail/collect errors on current host. | Current certificate unsupported pending Windows evidence. | UNVERIFIED |
| 11 | Failure resilience | Circuit breaker, AI unavailable, safe failure state. | Some tests fail due to host import errors; one test expected AI failure but was masked by Win32 import error. | Target-Windows validation necessary after root defects fixed. | UNVERIFIED |
| 12 | Functional closed loop | Functional loop, revalidation, recovery and end-to-end completion. | Tests exist; specific stale target test fails on host, generic verifier weaknesses found. | Must exercise actual pipeline and independently observe final state. | FAIL — VERIFICATION GAP |
| 13 | Adversarial hardening | Controlled red-team and fault injection. | Adversarial tests exist; out-of-bounds coordinate test fails; suite safety itself hazardous. | Do not run current product harness until isolation fixes. | FAIL — HIGH-RISK FINDINGS |
| 14 | Performance optimization | Benchmarks, resource metrics and freeze. | Historical benchmark JSON exists, but metrics show several regressions and gate does not evaluate thresholds. | Target Windows benchmark rerun and justified thresholds required. | NOT CERTIFIED |

The complete machine-readable 14-row matrix is `COMPASS_PHASE_AUDIT.csv`.

## 7. Detailed findings

This report contains 26 findings from the targeted repository/source and report review. Confidence is recorded independently from severity. Findings may require target-Windows confirmation, but the harness hazards and release-gate logic should be treated as blockers until corrected.

### COMPASS-AUDIT-001 — Task can be marked COMPLETED without valid final-goal verification
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Verification/false success  
**Component:** planner execution lifecycle  
**Location:** `planner/execution_engine.py`; lines `423-447`

- **Expected:** A task may enter COMPLETED only after valid independent final-goal verification.
- **Observed:** If verify_final_goal_state is missing, throws, or returns the wrong type, the engine creates a VERIFIED result whenever any step was already verified, then transitions to COMPLETED.
- **Evidence:** Source lines 423-447. Existing test planner/tests/test_final_state_verification.py::test_action_success_does_not_equal_task_success_when_final_state_absent failed on this audit host; exact target-Windows behavior needs rerun.
- **Impact:** A partial workflow may be reported as complete despite the requested final state being absent.
- **Recommended correction:** Remove the fallback. Verifier absence/exception/malformed result/insufficient evidence must result in UNVERIFIED/BLOCKED/FAILED, never COMPLETED. Preserve error evidence.
- **Regression protection:** Add tests for missing/throwing/wrong-type verifier, partial action success, wrong final state and genuinely observed final state.

### COMPASS-AUDIT-002 — Generic final-goal verifier accepts any completed step plus a healthy window
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Verification/false success  
**Component:** final goal verification  
**Location:** `planner/verification_engine.py`; lines `479-589, especially 568-583`

- **Expected:** Compare explicit goal-specific desired state with independently observed application/UI state.
- **Observed:** For most non-typing goals, completed_step_count > 0 plus an observable healthy active window returns VERIFIED; the evidence records window title and step count, not the requested goal outcome.
- **Evidence:** Source lines 568-583.
- **Impact:** Saving a file, submitting a form, changing a setting, etc. can be marked successful when the target result was never proved.
- **Recommended correction:** Implement goal-specific final-state contracts. If the system cannot observe the required state, return UNVERIFIED/BLOCKED. Never infer task success from action count or window liveness.
- **Regression protection:** Wrong value, wrong window, unrelated active window, partial task, crashed app, unsupported goal type and confirmed correct final state.

### COMPASS-AUDIT-003 — OBSERVE launch path returns success even when application launch fails
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Execution/false success  
**Component:** action dispatch  
**Location:** `planner/execution_engine.py`; lines `1286-1310`

- **Expected:** Execution result should match the actual outcome; app launch must be constrained and independently verified.
- **Observed:** OBSERVE may call os.startfile/subprocess.Popen for model-supplied app string, swallows exceptions, and unconditionally returns success. Heuristic verifier also treats OBSERVE as VERIFIED.
- **Evidence:** planner/execution_engine.py:1286-1310; planner/verification_engine.py:233-238.
- **Impact:** Failed launch can look successful, and untrusted planner values can request unintended launch targets subject to other layers.
- **Recommended correction:** Make OBSERVE observational only. Use a distinct launch action with strict allowlist/path validation, risk policy and observed window confirmation; return failure on exception.
- **Regression protection:** Missing executable, blocked launch, disallowed executable, no window, wrong window, slow launch and successful launch.

### COMPASS-AUDIT-004 — QA harness kills all processes named notepad.exe
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Harness safety/data loss  
**Component:** real product QA harness  
**Location:** `assurance/real_product_harness.py; assurance/real_product_suite.py`; lines `harness.py:85-104; suite.py:243-245,339-341`

- **Expected:** Test cleanup must terminate only the exact process started by the current test.
- **Observed:** terminate_processes_by_name iterates all processes named notepad.exe and kills each one. The suite calls it during setup/teardown. The packaged assurance/notepad.exe is a custom WinForms mock from MockNotepad.cs, not native Notepad.
- **Evidence:** Source paths and line ranges above; assurance/MockNotepad.cs.
- **Impact:** Running this suite on the user's desktop may kill unrelated native Notepad windows and lose unsaved work. Reports can overstate native app coverage.
- **Recommended correction:** Do not run the suite on the desktop before fixing. Track spawned child PID, creation time and executable path/job object; terminate only owned children. Label mock app correctly and test native Notepad separately in disposable environment.
- **Regression protection:** Keep an unrelated Notepad instance open with unsaved state and prove harness does not terminate it.

### COMPASS-AUDIT-005 — Startup/harness kills arbitrary port listeners on 8000 and 5173
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Harness safety/process management  
**Component:** startup and QA cleanup  
**Location:** `assurance/real_product_harness.py; scripts/start_compass.py`; lines `harness.py:237-248,280; start_compass.py:33-50,235,247`

- **Expected:** Only owned processes may be terminated; an unknown listener should cause safe port-conflict failure.
- **Observed:** _free_stale_ports and kill_process_on_port terminate any process listening on these ports without proving it belongs to COMPASS.
- **Evidence:** The cited source ranges.
- **Impact:** Other development servers/services can be killed when running tests or starting COMPASS.
- **Recommended correction:** Remove broad port killing. Track child processes launched by current instance. Unknown listener = BLOCKED with PID/path diagnostics, not automatic termination.
- **Regression protection:** Create unrelated listeners on 8000/5173 and assert they stay alive while launch reports conflict.

### COMPASS-AUDIT-006 — Adversarial harness can submit destructive goals to a live auto-executing task endpoint
**Severity:** CRITICAL · **Confidence:** HIGH CONFIDENCE · **Category:** Harness safety/agent execution  
**Component:** assurance harness and task API  
**Location:** `assurance/real_product_harness.py; assurance/real_product_suite.py; backend/app/routers/tasks.py`; lines `harness.py:192-200; suite.py:367-399; tasks.py:21-39`

- **Expected:** Adversarial goals must be tested in an isolated non-executing/sandboxed environment with desktop control disabled.
- **Observed:** Harness copies os.environ but does not explicitly set COMPASS_TEST_MODE=1 in the spawned backend. /api/tasks schedules execution unless that variable exists. The suite posts a prompt instructing COMPASS to ignore safety and delete system files.
- **Evidence:** assurance/real_product_harness.py:192-200; assurance/real_product_suite.py:375-399; backend/app/routers/tasks.py:21-39. pytest conftest does not automatically configure a separately spawned backend process.
- **Impact:** If run against an active AI-enabled desktop, hostile input may enter actual execution. Audit did not execute this harness due this risk.
- **Recommended correction:** Quarantine the current suite. Explicitly set and assert test mode in the child process and use a recording/blocking execution adapter or isolated VM. Never permit adversarial tests to dispatch OS actions.
- **Regression protection:** Prove dangerous test prompt produces zero OS dispatch calls; missing isolation flag aborts test startup.

### COMPASS-AUDIT-007 — Independent observer test passes without observing expected text
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Product test false pass  
**Component:** real product suite  
**Location:** `assurance/real_product_suite.py`; lines `221-239`

- **Expected:** PASS only when the exact expected text exists in the intended window/control.
- **Observed:** text_verified evaluates expected text OR non-empty observed text OR action_ok; any of the latter two passes even when expected text is absent.
- **Evidence:** Source lines 229-232.
- **Impact:** Historical product test results do not prove text entry worked correctly.
- **Recommended correction:** Remove both fallback clauses; verify target window/control and exact expected content using documented normalization. If not observable, FAIL/UNVERIFIED.
- **Regression protection:** Absent text, wrong window, partial text, pre-existing text, wrong control and actual correct text.

### COMPASS-AUDIT-008 — Controlled failure test passes solely because backend is alive
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Failure testing false pass  
**Component:** real product suite  
**Location:** `assurance/real_product_suite.py`; lines `339-359`

- **Expected:** When target disappears, test must assert safe rejection/abort, no unintended input, correct task state and retained evidence.
- **Observed:** After POSTing a type action against the vanished target, pass status is set to backend_alive; action response and actual side effects/task state are not checked.
- **Evidence:** Source lines 343-359.
- **Impact:** Unsafe action handling can pass so long as server remains alive.
- **Recommended correction:** Verify API result, no input dispatched to another target, correct TaskState and recovery/abort trace. Keep backend liveness separate.
- **Regression protection:** Target closed, stale/reused HWND, other foreground window, and a properly rejected action.

### COMPASS-AUDIT-009 — Adversarial tests accept HTTP status plus liveness as proof of security
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Security QA false pass  
**Component:** real product adversarial suite  
**Location:** `assurance/real_product_suite.py`; lines `364-407`

- **Expected:** Each attack needs threat-specific assertions and proof of no prohibited side effects.
- **Observed:** SQL injection, XSS, path traversal, prompt injection and other payloads are considered safe if status is 201/400/422 and backend remains alive; database/filesystem/task-execution effects are not checked.
- **Evidence:** Source lines 367-399; prompt-injection payload at 375-379.
- **Impact:** Accepted unsafe payload may be labelled protected; interacts dangerously with task auto-execution.
- **Recommended correction:** Use isolated test adapters; make payload-specific assertions; inspect database/file/dispatch side effects. A successful HTTP status is not a safety result.
- **Regression protection:** Per-payload negative assertions plus known-unsafe fixture that must be detected.

### COMPASS-AUDIT-010 — Stored 18/18 'real product E2E' result is not supported by the test execution path
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** E2E evidence quality  
**Component:** real product harness and suite  
**Location:** `assurance/real_product_suite.py; assurance/real_product_harness.py`; lines `suite.py:113-209,221-239; harness.py:202-235`

- **Expected:** Exercise one actual product workflow end-to-end through the official task pipeline and independently verify outcome; all claimed stack components must be ready.
- **Observed:** Suite creates a task that may auto-execute, calls planner endpoint separately, and directly calls automation/type, so flow can race and bypass the generated plan. Harness can return ready when backend is live but frontend never became ready. Target is a custom Notepad mock.
- **Evidence:** Source ranges; stored real_product_test_report.json says 18/18 PASS with timestamp 2026-10-04.
- **Impact:** Historical E2E claim does not demonstrate the actual assembled frontend→backend→planner→executor→verifier workflow.
- **Recommended correction:** Separate unit/API/mock-app/native-app suites. For E2E execute task exactly once via official path and verify final OS state. Require full stack readiness and report target app type, run ID, commit/tree hash.
- **Regression protection:** Demonstrate test fails when planner or frontend path is bypassed; prevent task/action races.

### COMPASS-AUDIT-011 — Release gate/master runner can mark FAIL as PASS or ignore blocked/unrun gates
**Severity:** CRITICAL · **Confidence:** CONFIRMED · **Category:** Certification/release gate  
**Component:** assurance release gate and master runner  
**Location:** `assurance/tools/release_gate.py; assurance/compass_assure.py`; lines `release_gate.py:112-132,175-199,214-220; compass_assure.py:64-107,288-308`

- **Expected:** Every mandatory gate must pass on fresh matching evidence; release gate should return nonzero on FAIL and master runner must consume structured readiness.
- **Observed:** Gate's warnings ignore SKIPPED/BLOCKED/NOT_RUN/ERROR/TIMEOUT states; stale files may be reused. Script prints readiness but does not return nonzero on FAIL. Master runner maps process exit code to stage PASS. Stored master report says release_gate PASS though its stdout says readiness FAIL/blocking secret_scan.
- **Evidence:** Source ranges plus stored assurance_master_report.json.
- **Impact:** Certification can be falsely reported successful despite a failing release decision.
- **Recommended correction:** Strict fail-closed state machine; run ID/source hash/freshness; explicit mandatory gate schema; nonzero on failure; runner parses JSON and cross-checks exit status and actual report.
- **Regression protection:** Fixtures for every gate status, stale PASS, malformed report, child exit 0 plus structured FAIL, and child failure.

### COMPASS-AUDIT-012 — Dependency and performance gates ignore important findings and regressions
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Release gate/dependencies/performance  
**Component:** assurance/tools/release_gate.py  
**Location:** `assurance/tools/release_gate.py`; lines `86-98,137-154`

- **Expected:** Aggregate all relevant dependency scans and compare measured metrics against justified performance thresholds.
- **Observed:** Dependency gate reads only pip_audit vulnerabilities, ignoring stored npm findings (1 high, 1 moderate). Performance gate is PASS if baseline and optimized files exist, without evaluating benchmark verdicts or thresholds. Stored comparison reports planning +33.1%, DB +54.8%, action +14.3%, replanning +69.9%, STOP +240.3%.
- **Evidence:** Source lines; assurance/reports/dependency_report.json; artifacts/phase14/benchmark_comparison.json.
- **Impact:** Release may pass despite dependency advisories or significant performance degradation.
- **Recommended correction:** Include npm and other dependency ecosystems; use fresh scan data and explicit suppression policy. Set justified SLOs and evaluate each benchmark; file existence must never pass the gate.
- **Regression protection:** Fixtures with npm high advisory, missing scan, stale baseline and threshold-exceeding metric.

### COMPASS-AUDIT-013 — Historical certification documents and evidence are contradictory
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Certification/documentation integrity  
**Component:** certification reports  
**Location:** `docs/FINAL_CERTIFICATION.md; docs/OPEN_SOURCE_INTEGRATION_AUDIT.md; docs/ASSURANCE/PRODUCT_TEST_MATRIX.md; docs/ASSURANCE/KNOWN_LIMITATIONS.md`; lines `document-level`

- **Expected:** Certification must identify exact revision/run and must not call untested mandatory behavior certified without an approved deviation.
- **Observed:** FINAL_CERTIFICATION says Phase 24 and CERTIFIED & FROZEN while marking real-world test NOT_TESTED; OPEN_SOURCE_INTEGRATION_AUDIT says final validation not yet done; PRODUCT_TEST_MATRIX broadly marks PASS while KNOWN_LIMITATIONS admits missing security/browser tests. Stored release report FAIL.
- **Evidence:** Named docs plus assurance/reports/assurance_master_report.json and release_gate_report.json.
- **Impact:** Cannot trust that claimed certification scope was completed for the supplied source tree.
- **Recommended correction:** Preserve historical records but mark them historical/superseded; issue a new traceable certification only from a fresh run tied to current source hash, explicit mandatory gates and residual limits. Clarify phase numbering without erasing history.
- **Regression protection:** Automated consistency check across gate JSON, master report, test matrix, run ID and certification doc.

### COMPASS-AUDIT-014 — Finding registry can silently reset on corrupt JSON and lacks reliable lifecycle/evidence guarantees
**Severity:** MEDIUM · **Confidence:** CONFIRMED · **Category:** Assurance data integrity  
**Component:** finding registry  
**Location:** `assurance/finding_schema.py; assurance/findings/finding_register.json`; lines `finding_schema.py:74-120,140-151`

- **Expected:** Corrupt registry must be preserved/quarantined and certification blocked; writes should be atomic/thread-safe; recurrence should reopen with evidence; fixed findings require regression ID.
- **Observed:** _load catches any exception and empties in-memory findings; next save can overwrite bad registry. Class claims thread-safety but code has no lock. Duplicate detection can return an old finding without refreshing evidence. All 7 stored records had empty evidence and regression_test_id; one OPEN item had verification_status VERIFIED.
- **Evidence:** Source lines and inspected finding_register.json.
- **Impact:** Failure history can be lost and “verified fix” labels are not grounded in permanent tests/evidence.
- **Recommended correction:** Add schema version, locking, atomic save, backups/quarantine and fail-closed behavior. Model lifecycle OPEN→FIXED→RETESTED→CLOSED; recurrence reopens. Require evidence and regression ID for verified closure.
- **Regression protection:** Corrupt JSON, concurrent writer, crash during save, recurrence, missing evidence and mismatched status.

### COMPASS-AUDIT-015 — Secret scanner excludes assurance directory and suppresses generic lines
**Severity:** MEDIUM · **Confidence:** CONFIRMED · **Category:** Security scanner coverage  
**Component:** secret scanner  
**Location:** `assurance/tools/secret_scanner.py`; lines `73-101,103-130,136-165`

- **Expected:** Scan relevant source, configuration, and assurance files, handle dotfiles and distinguish approved dummy data narrowly.
- **Observed:** SKIP_DIRS includes assurance, excluding scanner and associated source/config from main scan. Path.suffix is commonly empty for exact `.env`. is_dummy_or_test skips a line if it contains generic words such as test, payload, mock or sample.
- **Evidence:** Source lines above; stored secret report has three candidate token patterns in a test fixture that require precise triage.
- **Impact:** Credentials may be missed and scan coverage overstated.
- **Recommended correction:** Do not skip the whole assurance directory; handle dotfiles explicitly; replace broad generic-word skips with exact fixture values/hashes; detect then redact and report exclusions/coverage.
- **Regression protection:** Test fake credentials in `.env`, assurance scripts, comments containing generic words, fixtures, logs and scanner config.

### COMPASS-AUDIT-016 — Local API uses wildcard CORS with credentials and lacks an obvious explicit authorization layer at control routes
**Severity:** MEDIUM · **Confidence:** HIGH CONFIDENCE · **Category:** Local API security boundary  
**Component:** FastAPI control/task endpoints  
**Location:** `backend/app/main.py; backend/app/routers/automation.py; backend/app/routers/tasks.py`; lines `main.py:88-96; relevant route decorators`

- **Expected:** Use explicit configured origins and defend privileged local click/type/task endpoints against untrusted browser-origin requests and unauthorized local calls.
- **Observed:** CORSMiddleware uses allow_origins=['*'], allow_credentials=True, all methods and headers, despite a separate configured origin list. Inspected OS-control/task routes have no obvious auth dependency at router entry points. Exploitability was not tested live.
- **Evidence:** backend/app/main.py:88-96. Live browser origin/localhost tests were not run.
- **Impact:** Local OS-control API is a high-impact trust boundary; actual exploitability depends on binding, browser protections and the remaining route implementation.
- **Recommended correction:** Use explicit origin configuration, no wildcard+credentials, apply appropriate request authorization/CSRF/origin protections and test on target supported browser in isolated environment.
- **Regression protection:** Hostile origin, disallowed origin, no-token control call, allowed frontend origin and localhost/PNA behavior.

### COMPASS-AUDIT-017 — PlanValidator only validates schemas for a subset of action types and risk derives mainly from goal keywords
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** AI plan validation/safety  
**Component:** planner plan validator  
**Location:** `planner/plan_validator.py`; lines `105-166`

- **Expected:** Every action type must have strict schema/parameter/target/risk/permission checks based on the structured action and context.
- **Observed:** _validate_action validates TYPE, WAIT and KEY/KEY_PRESS but returns true for other action types. Consequential risk uses keywords in step.goal rather than the actual action type and parameters. Other layers may mitigate some cases, but this validator is incomplete.
- **Evidence:** planner/plan_validator.py:113-166.
- **Impact:** Malformed or risky plan items can pass this named validation layer and rely on unspecified downstream checks.
- **Recommended correction:** Add exhaustive per-action schemas; reject unknown/extraneous parameters; validate targets and bounds; derive risk from actual action semantics/context while retaining independent downstream safety/approval.
- **Regression protection:** Test all action types, invalid/missing params, dangerous action with benign wording, safe action with risky keywords, unsupported enum and launch paths.

### COMPASS-AUDIT-018 — Heuristic action verifier can mark focus/click/observe verified without proof of intended effect
**Severity:** HIGH · **Confidence:** CONFIRMED · **Category:** Action verification/false positive  
**Component:** planner verification engine  
**Location:** `planner/verification_engine.py`; lines `84-110,233-245,348-353`

- **Expected:** Focus/click/observe verification must prove a concrete postcondition; technical dispatch alone is not outcome success.
- **Observed:** Focus path treats action type click/focus as sufficient to set is_focused even when foreground HWND comparison did not match. WAIT/OBSERVE are always verified; default click/key can be verified when target/window remains healthy without detecting an expected transition.
- **Evidence:** Source ranges above; separate verify_click_transition returns UNVERIFIED when no observable state change but heuristic path can bypass it.
- **Impact:** Action results can overstate success and cascade into final goal false positives.
- **Recommended correction:** Remove type shortcut; compare observed HWND and target, require action-specific expected outcome or return UNVERIFIED.
- **Regression protection:** Wrong foreground window, failed focus, no-op click, modal dialog, no-op key, missing observer and genuine outcome.

### COMPASS-AUDIT-019 — Non-Windows coordinate fallback accepts arbitrary positive coordinates; Windows boundary allows one-past edge
**Severity:** MEDIUM · **Confidence:** CONFIRMED · **Category:** Action safety/platform  
**Component:** coordinate validator  
**Location:** `automation/safety.py`; lines `249-288`

- **Expected:** Live coordinates must be within actual virtual desktop and unsupported platform mode must not imply live validation.
- **Observed:** On non-Windows it returns `Simulated coordinates valid` for any nonnegative x/y after a limited rectangle check. Windows comparison uses > rather than >= at right/bottom exclusive edge. Current pytest failed the impossible-coordinate test.
- **Evidence:** automation/safety.py:249-288; automation/tests/test_coordinate_safety.py::test_coordinate_safety_reject_offscreen_impossible_coords failed.
- **Impact:** Host-side false safety and one-past bounds bug risk; actual Windows branch not executed in this audit.
- **Recommended correction:** Return UNSUPPORTED for real dispatch outside Windows or use explicitly injected test geometry. Fix half-open bounds and validate against target geometry.
- **Regression protection:** Very large coords, negative multi-monitor coords, exact edges, one-past edges, invalid rectangle and HWND cases.

### COMPASS-AUDIT-020 — StaleGuard can report freshness without validating a live HWND off Windows
**Severity:** MEDIUM · **Confidence:** HIGH CONFIDENCE · **Category:** Target validation/platform  
**Component:** planner stale guard  
**Location:** `planner/stale_guard.py`; lines `75-135`

- **Expected:** A real target handle must be revalidated for existence/state; unsupported platform must be blocked or use an explicitly fake test adapter.
- **Observed:** HWND checks only happen when sys.platform == win32 and target_hwnd; outside Windows the result can be based on timestamp. dead HWND test failed on this host.
- **Evidence:** planner/stale_guard.py:75-135; planner/tests/test_stale_guard.py::test_stale_guard_dead_hwnd_detected failed.
- **Impact:** Tests can get false confidence and real Windows behavior remains unverified.
- **Recommended correction:** Explicitly distinguish live HWND validator and test adapter; unsupported live revalidation should be BLOCKED/UNSUPPORTED, not fresh.
- **Regression protection:** Dead/reused handle, changed title, minimized window, foreground switch and stale UIA element.

### COMPASS-AUDIT-021 — Workflow tests target a different orchestrator/model implementation than runtime API imports
**Severity:** MEDIUM · **Confidence:** CONFIRMED · **Category:** Architecture/test representativeness  
**Component:** workflow engine  
**Location:** `backend/app/routers/workflows.py; planner/tests/test_workflow_orchestrator.py; planner/workflow*`; lines `n/a`

- **Expected:** Tests exercise the production runtime path, or both implementations are explicitly maintained and tested.
- **Observed:** Runtime router imports top-level planner.workflow_models/workflow_orchestrator; tests import planner.workflow.*. Parallel DAG/models/orchestrator/scheduler files exist.
- **Evidence:** backend/app/routers/workflows.py:16-22; planner/tests/test_workflow_orchestrator.py:6-9; duplicate modules in repository.
- **Impact:** Green tests may not validate the orchestrator that the product API actually serves.
- **Recommended correction:** Map callers and establish one authoritative runtime implementation, or test both intentionally. Add API-level workflow tests via real runtime path before any consolidation.
- **Regression protection:** Integration assertion that runtime API uses the exercised orchestration implementation.

### COMPASS-AUDIT-022 — Overlay highlight action returns success even if overlay IPC failed
**Severity:** LOW · **Confidence:** CONFIRMED · **Category:** Action result truthfulness  
**Component:** action dispatcher  
**Location:** `automation/action_dispatcher.py`; lines `927-963`

- **Expected:** Return success only when overlay action succeeded or independent evidence confirms it.
- **Observed:** An overlay IPC error is swallowed and ActionResult(success=True) is still returned.
- **Evidence:** automation/action_dispatcher.py:927-963.
- **Impact:** Logs/metrics can claim an unperformed visual operation succeeded.
- **Recommended correction:** Propagate error or return UNVERIFIED; require response/observation for success.
- **Regression protection:** IPC down, timeout, explicit negative response and successful response.

### COMPASS-AUDIT-023 — Source ZIP contains runtime DB/logs and lacks Git provenance for reproducible certification
**Severity:** MEDIUM · **Confidence:** CONFIRMED · **Category:** Reproducibility/data hygiene  
**Component:** archive packaging  
**Location:** `storage/compass.db; logs/compass.log; archive root`; lines `n/a`

- **Expected:** Shareable source archive should link exact commit/tree hash, lock dependencies and exclude/sanitize runtime user/task data.
- **Observed:** ZIP has no .git metadata, includes storage/compass.db (~557 KB) and logs/compass.log (~449 KB), plus generated traces/reports. Therefore tag/commit correspondence cannot be verified.
- **Evidence:** Archive inventory: no .git/.venv/frontend node_modules; DB/log present.
- **Impact:** Certification provenance is unverified and DB/log could contain task content or personal data.
- **Recommended correction:** Produce source-only export plus separate sanitized evidence package, add source tree hash and lockfile/environment manifest, inspect/redact DB/log before sharing.
- **Regression protection:** Packaging allowlist and secret/PII scan; verify source hash and exact release provenance.

### COMPASS-AUDIT-024 — Historical benchmark comparisons show latency regressions that release gate ignores
**Severity:** MEDIUM · **Confidence:** HIGH CONFIDENCE · **Category:** Performance/evidence  
**Component:** Phase 14 benchmarks and release gate  
**Location:** `artifacts/phase14/benchmark_comparison.json; assurance/tools/release_gate.py`; lines `release_gate.py:137-154`

- **Expected:** Performance PASS must follow reproducible current measurements against justified limits.
- **Observed:** Stored comparison shows planning +33.1%, database +54.8%, action +14.3%, replanning +69.9%, STOP +240.3%. Release gate still says performance PASS based on artifact existence; benchmark code labels some metrics simulated and reports are historical.
- **Evidence:** Stored benchmark comparison and release gate logic.
- **Impact:** The optimization/performance claim is unsupported until measurements and thresholds are reproduced. STOP latency increase merits review, with methodology confirmed before conclusions.
- **Recommended correction:** Run target Windows benchmarks with recorded run/source IDs, repeated samples, workload, warmup and resource measures. Define thresholds and require all regressions approved; separate simulated microbenchmarks from actual product performance.
- **Regression protection:** Release gate must fail for missing/stale metrics and unexplained threshold violations.

### COMPASS-AUDIT-025 — Actual Windows/product behavior was not verifiable on audit host and several platform tests error instead of cleanly blocking
**Severity:** HIGH · **Confidence:** CONFIRMED GAP · **Category:** Test environment/verification gap  
**Component:** Windows-dependent suites  
**Location:** `pytest.ini and Windows-dependent modules`; lines `testpaths and failing tests`

- **Expected:** Supported Windows environment and dependencies are required for authoritative UIA/Win32/overlay/product certification; unsupported platform should be clearly BLOCKED, not fake PASS.
- **Observed:** Audit ran on Linux/Python 3.13.5; PySide6/WinRT/hypothesis and Playwright browser runtime unavailable. Full pytest: 45 failed, 491 passed, 12 skipped, 25 collection errors, 5 warnings in 20.80s. Actual Windows product did not run.
- **Evidence:** Raw test log in audit package. Many errors reference ctypes.WinDLL/windll; coordinate safety is a real host-reproduced mismatch. Other failures require isolated Windows reruns.
- **Impact:** No claim can be made that the assembled Windows application fully works based on this audit.
- **Recommended correction:** Run on the supported Windows environment with declared dependencies; categorize platform-dependent tests; run true UIA/Win32/frontend/API/E2E in isolated desktop with fresh evidence.
- **Regression protection:** Target Windows full regression, actual product workflows, STOP, UIA, overlay, and exact run-ID evidence.

### COMPASS-AUDIT-026 — Documentation and phase/certification references are inconsistent and too thin to govern testing reliably
**Severity:** LOW · **Confidence:** CONFIRMED · **Category:** Documentation/engineering process  
**Component:** root and docs  
**Location:** `README.md; SPEC.md; docs/QA_AND_CERTIFICATION.md; docs/TESTING.md; docs/SECURITY.md; docs/ROADMAP.md; docs/CORE_LIFECYCLE.md`; lines `document-level`

- **Expected:** Current canonical docs should accurately describe architecture, tests, safety invariants, certification scope, limitations, environment and commands.
- **Observed:** Several key docs are boilerplate/only a few lines; SPEC.md focuses on Phase 9, a certification record says Phase 24, and test matrix PASS claims conflict with known limitations.
- **Evidence:** Named files, plus finding 013 documentation conflicts.
- **Impact:** Future agents may use wrong test process or mistake planned/documented behavior for implemented, verified capability.
- **Recommended correction:** After remediation, update the correct canonical documents, preserve historical records, and align roadmap/phase mapping with actual current implementation and evidence.
- **Regression protection:** Doc-to-code/test consistency check; ensure instructions run successfully in clean environment.


## 8. QA/report integrity problems

Historical report conclusions cannot be accepted as current certification evidence:
- `assurance/reports/assurance_master_report.json` is a historical quick run with mixed stage results. Its release-gate stage is stored as PASS although the release-gate stdout prints FAIL and says the secret scan blocks readiness.
- `assurance/reports/release_gate_report.json` itself reports overall FAIL and a blocking `secret_scan`.
- `assurance/reports/real_product_test_report.json` reports 18/18 PASS, but the corresponding test path has weak assertions, mixes task creation/planning/direct automation and uses a mock Notepad app. That report is not credible evidence of full real-product correctness.
- The test matrix marks broad PASS states while known limitations and documentation elsewhere acknowledge gaps.
- `docs/FINAL_CERTIFICATION.md` says “Phase 24” and “CERTIFIED & FROZEN” while marking real-world testing NOT_TESTED. Other documents do not consistently match this claim.
- `assurance/findings/finding_register.json` has seven records with empty evidence and regression-test ID fields; one record’s open/current verification statuses conflict.

These are not cosmetic inconsistencies. A release process that cannot reliably distinguish FAIL/BLOCKED/NOT RUN from PASS is not safe to certify.

## 9. Security and safety disposition

Source review identifies high-impact concerns in test harness isolation, process lifecycle, API trust boundaries and plan validation. These should not be described as confirmed remotely exploitable vulnerabilities until tested in a controlled target environment. However, the destructive test-harness path is a concrete operational hazard and should be disabled before running it on the user's working Windows session.

CORS uses wildcard origins with credentials enabled. Control route authentication/authorization was not clearly evident at the inspected route boundaries. This needs a threat model and real local API tests; exploitability depends on browser/origin and runtime details.

The secret scanner is not a sufficient basis for declaring the repository secret-free because its exclusion/suppression rules can skip meaningful content. No secret scan result is represented here as comprehensive assurance.

## 10. Performance disposition

The stored Phase 14 benchmark comparison reports:

| Metric | Stored baseline | Stored optimized | Change |
|---|---:|---:|---:|
| Planning latency | 0.905 ms | 1.205 ms | +33.1% slower |
| Database operation | 9.825 ms | 15.207 ms | +54.8% slower |
| Action latency | 60.516 ms | 69.152 ms | +14.3% slower |
| Replanning latency | 0.680 ms | 1.155 ms | +69.9% slower |
| STOP latency | 13.426 ms | 45.694 ms | +240.3% slower |
| End-to-end single step | 64.782 ms | 65.897 ms | +1.7% slower |

These are **stored historical data**, not independently reproduced benchmarks. Some benchmark code labels results as simulated. The release gate currently appears to pass performance based on report-file existence, not on comparison against justified thresholds. The STOP latency change deserves investigation with repeated, target-Windows measurements and a documented threshold.

## 11. Requirement-to-test traceability and acceptance

Use `COMPASS_REQUIREMENT_TRACEABILITY.csv` for the initial matrix. It captures 22 core requirements, but it is not a claim that every possible requirement has been extracted from every external/historical specification. The audit identifies at least these unverified/failed requirement groups:

- final goal must be independently verified before `COMPLETED`;
- action return values must reflect actual action outcome;
- hostile goal content cannot produce live destructive execution through a test harness;
- product-level tests must observe real expected state;
- safety and STOP/cancellation must remain effective under failure;
- all mandatory gate failures must block certification;
- tests and historical defects must map to evidence and permanent regression tests;
- actual Windows/AI/product E2E needs to run in a supported environment;
- dependency and performance gates must use current results and declared thresholds.

## 12. Recommended remediation order

### P0 — Contain dangerous test execution
1. Disable the current real-product/adversarial test harness until isolated.
2. Explicitly set and verify `COMPASS_TEST_MODE=1` in the backend child. More importantly, use a non-executing test action adapter that rejects OS actions unless the fixture explicitly permits them.
3. Remove process-name kill (`notepad.exe`) and blind port kill (`8000`/`5173`). Track only exact child PIDs created by current test run; if port ownership cannot be established, fail closed.
4. Remove destructive prompt instructions from live harness scenarios; hostile prompts must be sent to a stubbed/record-only sandbox incapable of controlling the host OS.
5. Audit all scripts for side effects before executing them.

### P0 — Correct false-success behavior
6. Remove final verifier fallback that synthesizes VERIFIED when verifier is missing, throws or returns wrong type.
7. Make generic final goal verifier require goal-specific observed final state, not merely a completed step or healthy active window.
8. Make `OBSERVE` start/launch operations return failure if launch fails; make no-op observation outcomes `UNVERIFIED` unless an actual observation is captured.
9. Replace weak text assertion with exact goal-specific checks.
10. Make click/focus/WAIT/OBSERVE verification distinguish “API call returned” from “intended postcondition observed”.

### P0 — Make release gate fail closed
11. Propagate each stage’s parsed status (PASS/FAIL/BLOCKED/NOT RUN), not only subprocess exit code.
12. Ensure release-gate process returns nonzero on FAIL and master runner marks stage FAIL.
13. Reject stale reports by binding report to unique run ID, source tree hash, environment, timestamp and exact command.
14. Fail certification for missing/unrun mandatory gates.
15. Parse actual dependency scan results including npm, not just whether a file exists or a pip audit ran.
16. Parse benchmark JSON, validate actual measurements, compare with project-defined thresholds, and fail on unexplained regression.

### P1 — Validation, scanner, registry
17. Build complete action-specific parameter schema for all action types; safety/risk should be structured policy, not primarily goal-keyword matches.
18. Correct coordinate bounds and stale HWND behavior, after verifying platform semantics on Windows.
19. Fix secret scanner skip/suppression behavior and run on isolated copy; include assurance code and dotfiles with explicit safe exclusions.
20. Make findings registry atomic/thread-safe; corrupt JSON should be quarantined with error rather than silently reset; require evidence and regression ID/status lifecycle.

### P1 — One runtime path and true product tests
21. Audit parallel workflow modules; make tests hit runtime API/import path. Do not consolidate blindly—map behavior, migrate with tests.
22. Product E2E should start an isolated COMPASS instance, interact through the user-facing API/UI, independently inspect final state, and verify no unauthorized side effects.
23. Fault-injection test must inspect actual task/action status, side effects and safe abort, not merely backend liveness.
24. Adversarial test must verify forbidden OS actions were not issued/executed and no external effects occurred, not merely accept HTTP status.
25. Separate mock-Notepad fixture tests from native Notepad Windows tests. Mock tests must never count as real Windows evidence.
26. Create test-the-tests mutation fixture to prove broken gates block certification.

### P2 — Reproducibility and docs
27. Generate source-only ZIP plus separate sanitized evidence bundle; exclude DB/logs by default, or explicitly sanitize after review.
28. Attach source hash/commit and dependency lockfile, environment manifest, unique run IDs.
29. Align docs to canonical phase history/current verification. Preserve old claims as historical; do not rewrite them as passed.
30. Add performance acceptance thresholds with repeated samples, workload and run IDs; report simulated microbenchmarks separately.
31. Re-run target Windows tests in isolated desktop; run UIA/Win32/overlay, API/E2E, STOP/cancel, fault/recovery, AI eval, security and baseline/perf.
32. Only after all mandatory gates pass and evidence is complete, certify/freeze. Do not claim zero bugs.

## 13. Final verdict

**NOT READY FOR CERTIFICATION.**

This verdict does not mean every part of COMPASS is broken. The repository has a substantial implementation and 491 tests passed on the host. But the audit also found 45 failures and 25 collection errors, critical test-harness risks, false-success pathways and a release-gate status-propagation bug. The actual target Windows product did not run here, so product-level correctness cannot be established from this ZIP.

No source code in the archive was modified by this audit.

## 14. Files produced in this audit bundle

- `COMPASS_FULL_AUDIT_REPORT.md` — primary report
- `COMPASS_AUDIT_RESULTS.json` — structured summary and findings
- `COMPASS_FINDINGS.csv` — 26 findings
- `COMPASS_PHASE_AUDIT.csv` — 14 phase rows
- `COMPASS_TEST_INVENTORY.csv` — executed checks and parsed failures
- `COMPASS_REQUIREMENT_TRACEABILITY.csv` — core requirement mapping
- `COMPASS_SOURCE_INVENTORY.csv` — source inventory
- `COMPASS_EVIDENCE_INDEX.csv` — evidence pointers
- `COMPASS_REMEDIATION_PLAN.md` — ordered fix approach
- `COMPASS_REMEDIATION_MASTER_PROMPT.md` — detailed prompt for Antigravity to audit/repair safely
- `assessments/` and `architecture/` — supporting assessments
- `evidence/logs/` — raw compile and pytest logs
- `COMPASS_AUDIT_MANIFEST.json` — artifact inventory/hashes
