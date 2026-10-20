# COMPASS Operational Daily Checklist

**Product:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Version:** 2.0.0  
**Document Location:** `docs/COMPASS_OPERATIONAL_CHECKLIST.md`  

---

## 1. Routine Pre-Flight & Startup Checklist

Before commencing daily operations with COMPASS:

- [ ] **Check Dependencies**: Ensure Python 3.11 and Node.js v18+ are available on the host machine.
- [ ] **Verify Port Availability**: Confirm ports `8000` (FastAPI) and `5173` (Vite) are not occupied by unrelated applications.
- [ ] **Target Application Preparation**: Launch the target application (e.g. Calculator, Notepad, or Browser) and position it visibly on the primary display.
- [ ] **Launch COMPASS**: Double-click `START_COMPASS.bat` or run `py -3.11 scripts/start_compass.py`.
- [ ] **Confirm Health Status**: Verify browser opens to `http://127.0.0.1:5173` and displays the green **System Healthy** badge.
- [ ] **Confirm Persistence**: Inspect **System Status** to verify SQLite database is in `WAL` mode with sub-50ms latency.

---

## 2. Safe Everyday Task Execution Checklist

During task submission and execution:

- [ ] **Goal Specificity**: Phrased goal clearly with explicit target application context (e.g. `"In Windows Notepad, insert meeting summary header"`).
- [ ] **Reversibility Check**: Ensure the proposed action does not alter critical system files or databases without prior review.
- [ ] **Operator Supervision**: Maintain visual observation of the target window while the task transitions through `OBSERVING` → `PLANNING` → `EXECUTING`.
- [ ] **StaleGuard Verification**: If window focus shifts during execution, confirm COMPASS pauses or brings the target application back into foreground.
- [ ] **Result Inspection**: Once task state reaches `COMPLETED`, inspect the output summary in the Task Card and verify the visual outcome in the target application.

---

## 3. Emergency Interception Checklist

If unexpected actions occur:

- [ ] **Stop Immediately**: Click the red **STOP** button on the Task Card or press `Esc` in the overlay HUD.
- [ ] **Verify Abort**: Check that task state transitions to `STOPPED` and mouse/keystroke synthesis stops within 150ms.
- [ ] **Inspect Audit Log**: Review the **Audit Log** view to determine the exact action that triggered the abort.

---

## 4. End-of-Day Shutdown Checklist

When concluding work with COMPASS:

- [ ] **Conclude Active Tasks**: Ensure all pending tasks have reached `COMPLETED`, `STOPPED`, or `FAILED` state.
- [ ] **Execute Clean Shutdown**: Run `STOP_COMPASS.bat` or `py -3.11 scripts/stop_compass.py`.
- [ ] **Confirm Port Release**: Verify ports `8000` and `5173` are released.
- [ ] **Confirm File Cleanup**: Confirm temporary `.compass_pids.json` has been unlinked.

---

## 5. Issue & Defect Reporting Checklist

When filing a bug or anomaly report:

- [ ] Record the Task UUID from the Task Card.
- [ ] Record target application name, version, and window title.
- [ ] Copy the full error message and stack trace from the Audit Log.
- [ ] Note whether the task was interrupted or reached completion.
- [ ] Follow change control guidelines before applying modifications.
