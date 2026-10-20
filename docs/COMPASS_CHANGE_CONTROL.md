# COMPASS Release Baseline & Change Control Protocol

**Product:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Release Identifier:** `2.0.0-verified.freeze`  
**Baseline Date:** October 18, 2026  
**Document Location:** `docs/COMPASS_CHANGE_CONTROL.md`  

---

## 1. Verified Release Baseline

This document establishes the official Change Control Policy for the verified COMPASS v2.0.0 software platform. All subsequent modifications, enhancements, or bug fixes must be evaluated against this baseline.

### 1.1 Baseline Configuration Parameters
- **Source Root**: `c:\Users\RAJATH U\Downloads\personal assitant`
- **Git Branch**: `master` (parent root `C:\Users\RAJATH U`, working-tree preserved)
- **Baseline Freeze Archive**: `C:\Users\RAJATH U\Downloads\compass_release_freeze_verified_20261018.zip`
- **Regression Pass Rate**: 806 passed, 2 skipped, 0 failed (808 Pytest total; 12/12 Vitest)
- **Frontend Build Status**: Clean production bundle (436 modules in 428ms, 0 errors)
- **Verified Applications**: Calculator (`calc.exe`), Notepad (`notepad.exe`), Paint (`mspaint.exe`), File Explorer (`explorer.exe`), Web Console (`http://127.0.0.1:5173`)

---

## 2. Policy Against Unnecessary Refactoring

To prevent accidental regressions, software drift, and degradation of verified capabilities:

> **CORE MANDATE**: Broad, speculative, or stylistic rewrites of working subsystems are strictly prohibited. The verified release state has passed formal empirical audit and must not be altered without a verified defect report or an authorized feature specification.

---

## 3. Mandatory Seven-Step Change Procedure

Any future code change to COMPASS must satisfy the following seven gates prior to merging or deployment:

1. **Clearly Identified Defect or Requirement**:
   - The change must reference an existing Defect ID (e.g. `DEF-009`) or an approved Feature Proposal with documented reproduction steps.
2. **Minimal & Focused Implementation**:
   - Code edits must be localized strictly to the affected component. Unrelated files, formatting, or dependencies must not be touched.
3. **Automated Unit & Regression Tests**:
   - Every bug fix must be accompanied by an automated regression test reproducing the original issue and demonstrating its resolution.
4. **Integration & Desktop Verification**:
   - If the modification touches perception, dispatch, or safety, it must be validated live against real Windows 11 target applications.
5. **Safety & Permission Review**:
   - Review whether the modification affects `RiskClassifier`, `CircuitBreaker`, or Human-in-the-Loop approval gates. Safety guardrails must never be relaxed.
6. **Comparison with Verified Baseline**:
   - Rerun the complete 808-test regression suite (`py -3.11 chatgpt_run_all_tests.py`) and confirm zero regressions against the 806-pass baseline.
7. **Pre-Change Backup**:
   - Generate a temporary incremental backup before applying modifications to enable immediate non-destructive rollback.

---

## 4. Rollback & Recovery Procedures

If a newly applied patch introduces a regression or instability:

1. **Non-Destructive Rollback**:
   - Identify the specific modified file(s).
   - Restore the verified baseline version directly from the verified freeze archive (`compass_release_freeze_verified_20261018.zip`).
   - Do NOT run destructive Git commands (`git reset --hard`, `git clean -fd`) that could destroy uncommitted workspace assets.
2. **Verification Following Rollback**:
   - Run `py -3.11 -m pytest tests/` to confirm that the codebase has returned to its clean baseline pass state.
   - Run `STOP_COMPASS.bat` followed by `START_COMPASS.bat` to verify runtime health.

---

## 5. Versioning Schema

All future versions must follow Semantic Versioning (SemVer 2.0.0):
- `2.0.0-verified.freeze`: Current frozen release baseline.
- `2.0.1`: Focused patch release addressing an isolated bug without schema or API alterations.
- `2.1.0`: Backward-compatible feature enhancement (e.g. new verified application integration).
- `3.0.0`: Major architectural revision (e.g. cross-platform macOS/Linux migration).
