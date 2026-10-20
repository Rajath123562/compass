# COMPASS — Core Closed-Loop Execution Lifecycle

## 1. Runtime Closed-Loop State Machine

COMPASS executes user goals through a continuous, adaptive closed loop:

```
UNDERSTAND
   ↓
PERCEIVE
   ↓
 PLAN
   ↓
VALIDATE
   ↓
SAFETY CHECK
   ↓
  ACT
   ↓
 VERIFY
   ↓
 ADAPT
   ↓
RE-PERCEIVE
```

1. **UNDERSTAND:** Ingests user goal, decomposes intent, and initializes the task state record in SQLite (`STARTING`).
2. **PERCEIVE:** Captures current foreground window, active UI Automation (UIA) tree hierarchy, and screen dimensions (`PLANNING`).
3. **PLAN:** Synthesizes candidate actions via the OmniRoute AI gateway or local rules engine.
4. **VALIDATE:** Verifies plan structure, parameter schemas, dependency DAGs, and consequential risk levels via `PlanValidator`.
5. **SAFETY CHECK:** Verifies screen coordinates against half-open virtual desktop boundaries, re-validates live window HWND freshness via `StaleGuard`, and evaluates human approval boundaries (`EXECUTING`).
6. **ACT:** Dispatches low-level Win32/UIA input events (click, type, key, scroll) or browser navigation actions.
7. **VERIFY:** Observes post-action UI transitions independently. Evaluates action-specific postconditions without relying on technical dispatch success alone (`VERIFYING`).
8. **ADAPT:** In the event of target drift, unexpected popups, or action failures, classifies failure category and triggers recovery or replanning.
9. **RE-PERCEIVE:** Refreshes window snapshot and advances to the next step, or transitions to `COMPLETED` once all goal-specific criteria are verified.

---

## 2. Engineering Quality & Assurance Contract

Every capability within COMPASS is governed by the mandatory engineering lifecycle contract:

```
PLAN
  ↓
IMPLEMENT
  ↓
TEST
  ↓
REAL-WORLD TEST
  ↓
FAILURE/RECOVERY TEST
  ↓
REGRESSION
  ↓
PERFORMANCE
  ↓
CERTIFY
  ↓
FREEZE
```

Continuous quality operates non-destructively: defects discovered in production or assurance trigger root-cause analysis, a minimal justified fix, and permanent regression test suites linked into the release gate.
