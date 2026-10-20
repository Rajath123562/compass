# COMPASS AGENT AUTONOMY & ACTION SAFETY REPORT

**Project:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Safety Standard:** Autonomous AI Safety Boundaries & Safe Execution Governance  
**Date:** October 18, 2026  

---

## 1. The 9-Stage Agent Control Loop

COMPASS executes tasks through a formal, 9-stage closed-loop architecture:

$$\text{UNDERSTAND} \rightarrow \text{PERCEIVE} \rightarrow \text{PLAN} \rightarrow \text{VALIDATE} \rightarrow \text{SAFETY CHECK} \rightarrow \text{ACT} \rightarrow \text{VERIFY} \rightarrow \text{ADAPT} \rightarrow \text{RE-PERCEIVE}$$

```
                ┌──────────────┐
                │  UNDERSTAND  │◄── Goal Intent & Ambiguity Check
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │   PERCEIVE   │◄── Win32 UIA Tree & Screenshot Capture
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │     PLAN     │◄── Task Decomposition & Dependency Graph
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │   VALIDATE   │◄── Element Resolution & Bounds Check
                └──────┬───────┘
                       ▼
          ┌───────────────────────────┐
          │  SAFETY CHECK & APPROVAL  │◄── Risk Evaluation & Human Gateway
          └────────────┬──────────────┘
                       ▼
                ┌──────────────┐
                │     ACT      │◄── Low-Level Native Windows Input Dispatch
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │    VERIFY    │◄── Evidence-Grounded Postcondition Check
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │    ADAPT     │◄── Dynamic Failure Recovery & Replanning
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ RE-PERCEIVE  │───► Cycles to Next Step or Completion
                └──────────────┘
```

---

## 2. Risk Tiering & Autonomy Boundaries

COMPASS categorizes every planned action into three distinct risk tiers:

| Risk Tier | Actions Included | Autonomous Execution Allowed? | Mandatory Human Confirmation Required? |
| :--- | :--- | :---: | :---: |
| **LOW** | Window Focus, Scroll, Read/Observe, Harmless Click (menus, tabs, navigation) | **YES** | No (unless in `GUIDE` mode) |
| **MEDIUM** | Form Input, Text Typing in Document, Non-destructive Button Click | **YES** (in `AUTONOMOUS` mode) | Optional (mode-dependent: `CONFIRM`/`ASSIST`) |
| **HIGH** | File Deletion, Terminal Command Execution, External Submissions, Financial, System Settings | **NO (STRICTLY PROHIBITED)** | **UNCONDITIONALLY MANDATORY** across all modes |

---

## 3. Anti-Bypass Enforcement at the Tool Boundary

A critical security requirement is that safety boundaries must NOT rely solely on LLM prompt instructions. In COMPASS:
1. **Execution Boundary Checks:** The `ExecutionEngine` and `HumanApprovalController` inspect the concrete action parameters, target window, and action type at the dispatch boundary.
2. **Rephrasing Resistance:** Even if an LLM is prompted to classify a destructive action as "harmless" (e.g., claiming `del C:\*.*` is "just a cache cleanup"), the underlying `ActionDispatcher` and `SafetyGuards` intercept the system call independently of the model's description.
3. **State-Bound Tokens:** Approval requests generate cryptographic, state-bound approval tokens tied to the exact window HWND, target bounds, and timestamp. A token cannot be reused for a different action or after window state mutation.

---

## 4. Emergency STOP Mechanism & Cancellation Integrity

The emergency STOP mechanism was verified across 12 distinct test scenarios:
- **Instantaneous Signal Propagation:** Calling `engine.stop_task()` sets a thread-safe `threading.Event`, which breaks out of observation, planning, waiting confirmation, and dispatch loops within milliseconds.
- **Terminal State Immutability:** Once a task reaches `STOPPED` or `CANCELLED`, any late AI responses, delayed worker threads, or secondary API calls are discarded. The state cannot transition to `COMPLETED` or `ACTING`.
- **Resource Cleanup:** All held UI Automation handles, active Playwright browser contexts, and child processes are terminated cleanly upon STOP.
