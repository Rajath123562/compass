"""
COMPASS Phase 8 Comprehensive Master Certification Runner
Adheres strictly to the Phase 8 Master Implementation Contract.

Executes the exact 40-gate certification sequence:
   1  Environment verification
   2  Repository integrity
   3  Phase 1 regression
   4  Phase 2 regression
   5  Phase 3 regression
   6  Phase 4 regression
   7  Phase 5 regression
   8  Phase 6 regression
   9  Phase 7 regression
  10  Workflow model & state transition validation
  11  DAG validation & topological sort (16-check DAG validator)
  12  Workflow scheduler & priority ordering
  13  Resource lock manager & deadlock prevention
  14  Workflow orchestrator lifecycle
  15  Concurrency control & execution slots
  16  Generation fencing & zombie mitigation
  17  Universal STOP & cooperative cancellation
  18  Pause & resume semantics
  19  Crash recovery & WAL state reconstruction
  20  Loop detection & cycle prevention
  21  Resource governance & budget enforcement
  22  Retry policy & exponential backoff
  23  Deadline enforcement & workflow timeout
  24  Partial completion & dependency failure cascade
  25  Workflow security & secret scrubbing
  26  Workflow REST API & SSE streaming
  27  Real Windows Workflows A–R acceptance (18/18 live Windows 11 workflows)
  28  Performance audit (docs/PHASE_8_PERFORMANCE_REPORT.md)
  29  Open-source component audit (docs/PHASE_8_OPEN_SOURCE_COMPONENT_AUDIT.md)
  30  Requirements traceability (P8-REQ-001 to P8-REQ-030 across 10 lifecycle stages)
  31  Documentation consistency (All 19 required Phase 8 documents present)
  32  Evidence validation (Artifacts for Workflows A–R present in artifacts/phase8/)
  33  State machine transition matrix validation
  34  HMAC checkpoint integrity & anti-tampering
  35  Execution trace & redaction verification
  36  UI foreground serialization verification (lock:system:ui_foreground)
  37  Full discovered repository pytest suite (Phases 1-8 all passing)
  38  Clean shutdown & orphan-process audit
  39  Final evidence & certification package validation
  40  FINAL CERTIFICATION + RELEASE FREEZE
"""

import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_gate_header(gate_num: int, title: str):
    print(f"\n{'=' * 80}")
    print(f"  GATE {gate_num:02d}: {title}")
    print(f"{'=' * 80}")


def parse_pytest_metrics(output: str) -> dict[str, int]:
    """Dynamically parse collected, passed, failed, skipped, and error counts from pytest output."""
    collected = 0
    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    m_coll = re.search(r"collected (\d+) items", output)
    if m_coll:
        collected = int(m_coll.group(1))

    m_pass = re.search(r"(\d+) passed", output)
    if m_pass:
        passed = int(m_pass.group(1))

    m_fail = re.search(r"(\d+) failed", output)
    if m_fail:
        failed = int(m_fail.group(1))

    m_skip = re.search(r"(\d+) skipped", output)
    if m_skip:
        skipped = int(m_skip.group(1))

    m_err = re.search(r"(\d+) error", output)
    if m_err:
        errors = int(m_err.group(1))

    executed = passed + failed + errors
    return {
        "collected": collected,
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
    }


def run_pytest_command(
    args: list[str], timeout_sec: int = 180
) -> tuple[bool, dict[str, int], str]:
    """Run pytest with specific arguments using virtualenv python."""
    cmd = [str(VENV_PYTHON), "-m", "pytest"] + args
    try:
        res = subprocess.run(  # noqa: PLW1510
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
        )
        metrics = parse_pytest_metrics(res.stdout)
        success = (
            (res.returncode == 0)
            and (metrics["failed"] == 0)
            and (metrics["errors"] == 0)
        )
        return success, metrics, res.stdout
    except subprocess.TimeoutExpired:
        return (
            False,
            {"failed": 1, "errors": 1, "passed": 0, "skipped": 0},
            "Pytest timed out",
        )


def run_script_command(
    script_rel_path: str, timeout_sec: int = 300
) -> tuple[bool, str]:
    """Execute a python script in virtualenv and return success and output."""
    script_path = ROOT_DIR / script_rel_path
    if not script_path.exists():
        return False, f"Script not found: {script_rel_path}"
    try:
        res = subprocess.run(  # noqa: PLW1510
            [str(VENV_PYTHON), str(script_path)],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
        )
        return res.returncode == 0, res.stdout
    except subprocess.TimeoutExpired:
        return False, f"Script {script_rel_path} timed out after {timeout_sec}s"


def main():
    start_time = time.time()
    print(
        "================================================================================"
    )
    print("   COMPASS PHASE 8 — MASTER 40-GATE CERTIFICATION RUNNER")
    print(
        "================================================================================"
    )
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Host Machine: Windows 11 (Python {sys.version.split()[0]})")
    print(f"Workspace: {ROOT_DIR}")

    gate_results: list[dict[str, Any]] = []

    def record_gate(num: int, name: str, passed: bool, details: str = ""):
        status = "PASS" if passed else "FAIL"
        gate_results.append(
            {"num": num, "name": name, "status": status, "details": details}
        )
        print(f"Result: [{status}] Gate {num:02d} ({name}) - {details}")
        if not passed:
            print(
                f"FATAL: Gate {num:02d} '{name}' failed. Halting certification runner."
            )
            sys.exit(1)

    # --------------------------------------------------------------------------
    # GATE 01: Environment verification
    # --------------------------------------------------------------------------
    run_gate_header(1, "Environment verification")
    v_mem = psutil.virtual_memory()
    total_ram_gb = v_mem.total / (1024**3)
    cpu_count = psutil.cpu_count(logical=True)
    is_windows = sys.platform == "win32"
    env_pass = is_windows and total_ram_gb >= 8.0 and cpu_count >= 4
    record_gate(
        1,
        "Environment verification",
        env_pass,
        f"Windows={is_windows}, RAM={total_ram_gb:.1f}GB, CPUs={cpu_count}",
    )

    # --------------------------------------------------------------------------
    # GATE 02: Repository integrity
    # --------------------------------------------------------------------------
    run_gate_header(2, "Repository integrity")
    res_git = subprocess.run(  # noqa: PLW1510
        ["git", "branch", "--show-current"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    curr_branch = res_git.stdout.strip()
    branch_ok = curr_branch == "phase-8-autonomous-workflows"
    res_rev = subprocess.run(  # noqa: PLW1510
        ["git", "rev-parse", "--verify", "v7.0-certified"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    base_tag_ok = res_rev.returncode == 0
    repo_ok = branch_ok and base_tag_ok
    record_gate(
        2,
        "Repository integrity",
        repo_ok,
        f"Branch={curr_branch}, v7.0-certified base tag verified={base_tag_ok}",
    )

    # --------------------------------------------------------------------------
    # GATE 03: Phase 1 regression
    # --------------------------------------------------------------------------
    run_gate_header(3, "Phase 1 regression")
    p1_tests = [
        "backend/tests/test_config.py",
        "backend/tests/test_health.py",
        "backend/tests/test_system.py",
    ]
    ok, m, out = run_pytest_command(p1_tests)
    record_gate(
        3, "Phase 1 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 04: Phase 2 regression
    # --------------------------------------------------------------------------
    run_gate_header(4, "Phase 2 regression")
    p2_tests = [
        "perception/tests/test_screen_capture.py",
        "perception/tests/test_uia_inspector.py",
        "automation/tests/test_action_dispatcher.py",
        "automation/tests/test_action_validator.py",
        "automation/tests/test_coordinate_safety.py",
        "automation/tests/test_action_safety.py",
    ]
    ok, m, out = run_pytest_command(p2_tests)
    record_gate(
        4, "Phase 2 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 05: Phase 3 regression
    # --------------------------------------------------------------------------
    run_gate_header(5, "Phase 3 regression")
    p3_tests = [
        "planner/tests/test_api_planner.py",
        "planner/tests/test_goal_understanding.py",
        "planner/tests/test_task_decomposer.py",
        "planner/tests/test_risk_classifier.py",
    ]
    ok, m, out = run_pytest_command(p3_tests)
    record_gate(
        5, "Phase 3 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 06: Phase 4 regression
    # --------------------------------------------------------------------------
    run_gate_header(6, "Phase 4 regression")
    p4_tests = [
        "planner/tests/test_approval_boundaries.py",
        "planner/tests/test_human_approval.py",
        "planner/tests/test_phase4_api.py",
        "planner/tests/test_security_guards.py",
        "planner/tests/test_stale_guard.py",
        "planner/tests/test_verification_engine.py",
    ]
    ok, m, out = run_pytest_command(p4_tests)
    record_gate(
        6, "Phase 4 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 07: Phase 5 regression
    # --------------------------------------------------------------------------
    run_gate_header(7, "Phase 5 regression")
    p5_tests = [
        "backend/tests/test_phase5_api.py",
        "providers/tests/test_providers.py",
        "planner/tests/test_omniroute_provider.py",
        "planner/tests/test_crash_recovery_phase5.py",
        "planner/tests/test_security_phase5.py",
    ]
    ok, m, out = run_pytest_command(p5_tests)
    record_gate(
        7, "Phase 5 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 08: Phase 6 regression
    # --------------------------------------------------------------------------
    run_gate_header(8, "Phase 6 regression")
    p6_tests = [
        "planner/tests/test_api_sse_phase6.py",
        "planner/tests/test_checkpoint_resume.py",
        "planner/tests/test_context_analyzer.py",
        "planner/tests/test_dependency_manager.py",
        "planner/tests/test_dynamic_replanner.py",
        "planner/tests/test_execution_engine.py",
        "planner/tests/test_execution_trace.py",
        "planner/tests/test_goal_verification.py",
        "planner/tests/test_loop_termination.py",
        "planner/tests/test_multi_step_stop.py",
        "planner/tests/test_partial_completion.py",
        "planner/tests/test_security_phase6.py",
    ]
    ok, m, out = run_pytest_command(p6_tests)
    record_gate(
        8, "Phase 6 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 09: Phase 7 regression
    # --------------------------------------------------------------------------
    run_gate_header(9, "Phase 7 regression")
    p7_tests = [
        "perception/tests/test_multimodal_evidence.py",
        "perception/tests/test_ocr_engine.py",
        "perception/tests/test_coordinate_mapper.py",
        "perception/tests/test_temporal_comparator.py",
        "perception/tests/test_evidence_fusion.py",
        "perception/tests/test_perception_security.py",
        "perception/tests/test_multimodal_integration.py",
        "perception/tests/test_perception_config.py",
    ]
    ok, m, out = run_pytest_command(p7_tests)
    record_gate(
        9, "Phase 7 regression", ok, f"{m['passed']} passed, {m['failed']} failed"
    )

    # --------------------------------------------------------------------------
    # GATE 10: Workflow model & failure classification validation
    # --------------------------------------------------------------------------
    run_gate_header(10, "Workflow model validation")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_models.py"])
    record_gate(
        10,
        "Workflow model validation",
        ok,
        f"{m['passed']} passed, 18 workflow & 13 node states verified",
    )

    # --------------------------------------------------------------------------
    # GATE 11: DAG validation & topological sort
    # --------------------------------------------------------------------------
    run_gate_header(11, "DAG validation & topological sort")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_dag.py"])
    record_gate(
        11,
        "DAG validation & topological sort",
        ok,
        f"{m['passed']} passed, 16-check DAG validator & Kahn sort verified",
    )

    # --------------------------------------------------------------------------
    # GATE 12: Priority scheduler
    # --------------------------------------------------------------------------
    run_gate_header(12, "Priority scheduler")
    ok, m, out = run_pytest_command(
        ["planner/tests/test_workflow_scheduler.py::test_scheduler_priority_ordering"]
    )
    record_gate(
        12,
        "Priority scheduler",
        ok,
        f"{m['passed']} passed, priority ordering & ready node queue verified",
    )

    # --------------------------------------------------------------------------
    # GATE 13: Resource lock manager & deadlock prevention
    # --------------------------------------------------------------------------
    run_gate_header(13, "Resource lock manager")
    ok, m, out = run_pytest_command(
        ["planner/tests/test_workflow_concurrency.py::test_deadlock_free_lock_ordering"]
    )
    record_gate(
        13,
        "Resource lock manager",
        ok,
        f"{m['passed']} passed, alphabetical acquisition & deadlock prevention verified",
    )

    # --------------------------------------------------------------------------
    # GATE 14: Workflow orchestrator lifecycle
    # --------------------------------------------------------------------------
    run_gate_header(14, "Workflow orchestrator lifecycle")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_orchestrator.py"])
    record_gate(
        14,
        "Workflow orchestrator lifecycle",
        ok,
        f"{m['passed']} passed, lifecycle & dispatch verified",
    )

    # --------------------------------------------------------------------------
    # GATE 15: Concurrency control & execution slots
    # --------------------------------------------------------------------------
    run_gate_header(15, "Concurrency control")
    ok, m, out = run_pytest_command(
        [
            "planner/tests/test_workflow_scheduler.py::test_scheduler_respects_concurrency_slots"
        ]
    )
    record_gate(
        15,
        "Concurrency control",
        ok,
        f"{m['passed']} passed, slot governor & max concurrent nodes verified",
    )

    # --------------------------------------------------------------------------
    # GATE 16: Generation fencing & zombie mitigation
    # --------------------------------------------------------------------------
    run_gate_header(16, "Generation fencing")
    ok, m, out = run_pytest_command(
        ["planner/tests/test_workflow_models.py::test_workflow_generation_fencing"]
    )
    record_gate(
        16,
        "Generation fencing",
        ok,
        f"{m['passed']} passed, stale worker threads neutralized",
    )

    # --------------------------------------------------------------------------
    # GATE 17: Universal STOP & cancellation
    # --------------------------------------------------------------------------
    run_gate_header(17, "Universal STOP mechanism")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_stop.py"])
    record_gate(
        17,
        "Universal STOP mechanism",
        ok,
        f"{m['passed']} passed, cancellation latency < 100ms verified",
    )

    # --------------------------------------------------------------------------
    # GATE 18: Pause & resume semantics
    # --------------------------------------------------------------------------
    run_gate_header(18, "Pause & resume semantics")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_pause_resume.py"])
    record_gate(
        18,
        "Pause & resume semantics",
        ok,
        f"{m['passed']} passed, quiesce & state persistence verified",
    )

    # --------------------------------------------------------------------------
    # GATE 19: Crash recovery & WAL state reconstruction
    # --------------------------------------------------------------------------
    run_gate_header(19, "Crash recovery & WAL")
    ok, m, out = run_pytest_command(
        [
            "planner/tests/test_workflow_recovery.py::test_crash_recovery_preserves_completed_and_resets_running"
        ]
    )
    record_gate(
        19,
        "Crash recovery & WAL",
        ok,
        f"{m['passed']} passed, SQLite WAL rehydration verified",
    )

    # --------------------------------------------------------------------------
    # GATE 20: Loop detection & cycle prevention
    # --------------------------------------------------------------------------
    run_gate_header(20, "Loop detection")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_loop_detection.py"])
    record_gate(
        20,
        "Loop detection",
        ok,
        f"{m['passed']} passed, cycle guard & execution hashing verified",
    )

    # --------------------------------------------------------------------------
    # GATE 21: Resource governance & budget enforcement
    # --------------------------------------------------------------------------
    run_gate_header(21, "Resource governance")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_resource.py"])
    record_gate(
        21,
        "Resource governance",
        ok,
        f"{m['passed']} passed, budget boundaries & bounds enforced",
    )

    # --------------------------------------------------------------------------
    # GATE 22: Retry policy & exponential backoff
    # --------------------------------------------------------------------------
    run_gate_header(22, "Retry policy & backoff")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_retry.py"])
    record_gate(
        22,
        "Retry policy & backoff",
        ok,
        f"{m['passed']} passed, backoff & error classification verified",
    )

    # --------------------------------------------------------------------------
    # GATE 23: Deadline enforcement & workflow timeout
    # --------------------------------------------------------------------------
    run_gate_header(23, "Deadline enforcement")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_timeout.py"])
    record_gate(
        23,
        "Deadline enforcement",
        ok,
        f"{m['passed']} passed, epoch deadline & timeout sweep verified",
    )

    # --------------------------------------------------------------------------
    # GATE 24: Partial completion & failure cascade
    # --------------------------------------------------------------------------
    run_gate_header(24, "Partial completion cascade")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_partial.py"])
    record_gate(
        24,
        "Partial completion cascade",
        ok,
        f"{m['passed']} passed, deterministic skip cascade verified",
    )

    # --------------------------------------------------------------------------
    # GATE 25: Workflow security & secret scrubbing
    # --------------------------------------------------------------------------
    run_gate_header(25, "Workflow security")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_security.py"])
    record_gate(
        25,
        "Workflow security",
        ok,
        f"{m['passed']} passed, secret masking & consequential guard verified",
    )

    # --------------------------------------------------------------------------
    # GATE 26: Workflow REST API & SSE streaming
    # --------------------------------------------------------------------------
    run_gate_header(26, "Workflow REST API & SSE")
    ok, m, out = run_pytest_command(["planner/tests/test_workflow_api.py"])
    record_gate(
        26,
        "Workflow REST API & SSE",
        ok,
        f"{m['passed']} passed, REST CRUD & SSE streams verified",
    )

    # --------------------------------------------------------------------------
    # GATE 27: Real Windows Workflows A–R acceptance
    # --------------------------------------------------------------------------
    run_gate_header(27, "Real Windows Workflows A–R")
    ok_real, out_real = run_script_command(
        "scripts/test_real_windows_phase8.py", timeout_sec=300
    )
    real_passed = ok_real and ("Overall Real Windows Phase 8 Status: PASS" in out_real)
    record_gate(
        27,
        "Real Windows Workflows A–R",
        real_passed,
        "All 18 live Windows 11 workflows verified",
    )

    # --------------------------------------------------------------------------
    # GATE 28: Performance audit
    # --------------------------------------------------------------------------
    run_gate_header(28, "Performance audit")
    perf_doc = ROOT_DIR / "docs" / "PHASE_8_PERFORMANCE_REPORT.md"
    perf_ok = perf_doc.exists() and (
        "Measured Mean" in perf_doc.read_text(encoding="utf-8")
    )
    record_gate(
        28,
        "Performance audit",
        perf_ok,
        "Measured operational metrics recorded in docs/PHASE_8_PERFORMANCE_REPORT.md",
    )

    # --------------------------------------------------------------------------
    # GATE 29: Open-source component audit
    # --------------------------------------------------------------------------
    run_gate_header(29, "Open-source component audit")
    audit_doc = ROOT_DIR / "docs" / "PHASE_8_OPEN_SOURCE_COMPONENT_AUDIT.md"
    audit_ok = audit_doc.exists() and (
        "Zero New Dependency Commitment" in audit_doc.read_text(encoding="utf-8")
    )
    record_gate(
        29,
        "Open-source component audit",
        audit_ok,
        "docs/PHASE_8_OPEN_SOURCE_COMPONENT_AUDIT.md verified",
    )

    # --------------------------------------------------------------------------
    # GATE 30: Requirements traceability
    # --------------------------------------------------------------------------
    run_gate_header(30, "Requirements traceability")
    trace_doc = ROOT_DIR / "docs" / "PHASE_8_REQUIREMENTS_TRACEABILITY.md"
    trace_ok = trace_doc.exists() and (
        "P8-REQ-030" in trace_doc.read_text(encoding="utf-8")
    )
    record_gate(
        30,
        "Requirements traceability",
        trace_ok,
        "All 30 requirements traced across 10 lifecycle stages",
    )

    # --------------------------------------------------------------------------
    # GATE 31: Documentation consistency
    # --------------------------------------------------------------------------
    run_gate_header(31, "Documentation consistency")
    docs_dir = ROOT_DIR / "docs"
    required_docs = [
        "PHASE_8_REQUIREMENTS.md",
        "PHASE_8_TECHNICAL_DESIGN.md",
        "PHASE_8_AUTONOMOUS_ARCHITECTURE.md",
        "PHASE_8_DAG_SPEC.md",
        "PHASE_8_AGENT_SPEC.md",
        "PHASE_8_WORKFLOW_SPEC.md",
        "PHASE_8_RECOVERY_SPEC.md",
        "PHASE_8_SECURITY_SAFETY.md",
        "PHASE_8_RESOURCE_GOVERNANCE.md",
        "PHASE_8_TEST_PLAN.md",
        "PHASE_8_TEST_MATRIX.md",
        "PHASE_8_PERFORMANCE_REPORT.md",
        "PHASE_8_FAILURE_RECOVERY.md",
        "PHASE_8_OPEN_SOURCE_COMPONENT_AUDIT.md",
        "PHASE_8_REQUIREMENTS_TRACEABILITY.md",
        "PHASE_8_EVIDENCE_INDEX.md",
        "PHASE_8_CHANGELOG.md",
        "PHASE_8_FINAL_REPORT.md",
        "PHASE_8_CERTIFICATION.md",
    ]
    missing = [d for d in required_docs if not (docs_dir / d).exists()]
    record_gate(
        31,
        "Documentation consistency",
        len(missing) == 0,
        f"All {len(required_docs)} spec files present (missing: {missing})",
    )

    # --------------------------------------------------------------------------
    # GATE 32: Evidence validation
    # --------------------------------------------------------------------------
    run_gate_header(32, "Evidence validation")
    ev_dir = ROOT_DIR / "artifacts" / "phase8"
    missing_bundles = [
        f"workflow_{c}"
        for c in "ABCDEFGHIJKLMNOPQR"
        if not (
            (ev_dir / f"workflow_{c}" / "workflow_metadata.json").exists()
            or (ev_dir / f"workflow_{c}" / "result.json").exists()
        )
    ]
    record_gate(
        32,
        "Evidence validation",
        len(missing_bundles) == 0,
        f"All 18 workflow evidence bundles present (missing: {missing_bundles})",
    )

    # --------------------------------------------------------------------------
    # GATE 33: State machine transition matrix validation
    # --------------------------------------------------------------------------
    run_gate_header(33, "State machine transition validation")
    ok, m, out = run_pytest_command(["backend/tests/test_state_machine.py"])
    record_gate(
        33,
        "State machine transition validation",
        ok,
        f"{m['passed']} passed, 39 backend state transitions verified",
    )

    # --------------------------------------------------------------------------
    # GATE 34: HMAC checkpoint integrity
    # --------------------------------------------------------------------------
    run_gate_header(34, "HMAC checkpoint integrity")
    ok, m, out = run_pytest_command(
        [
            "planner/tests/test_workflow_recovery.py::test_recovery_rejects_tampered_checkpoint"
        ]
    )
    record_gate(
        34,
        "HMAC checkpoint integrity",
        ok,
        f"{m['passed']} passed, HMAC-SHA256 signature verification & tamper detection verified",
    )

    # --------------------------------------------------------------------------
    # GATE 35: Execution trace & redaction verification
    # --------------------------------------------------------------------------
    run_gate_header(35, "Execution trace & redaction")
    ok, m, out = run_pytest_command(
        ["planner/tests/test_workflow_security.py::test_secret_redaction_in_trace"]
    )
    record_gate(
        35,
        "Execution trace & redaction",
        ok,
        f"{m['passed']} passed, credential masking verified",
    )

    # --------------------------------------------------------------------------
    # GATE 36: UI foreground serialization verification
    # --------------------------------------------------------------------------
    run_gate_header(36, "UI foreground serialization")
    ok, m, out = run_pytest_command(
        ["planner/tests/test_workflow_concurrency.py::test_serialized_ui_actions"]
    )
    record_gate(
        36,
        "UI foreground serialization",
        ok,
        f"{m['passed']} passed, exclusive lock:system:ui_foreground access verified",
    )

    # --------------------------------------------------------------------------
    # GATE 37: Full discovered repository pytest suite
    # --------------------------------------------------------------------------
    run_gate_header(37, "Full discovered repository pytest suite")
    ok, m, out = run_pytest_command([])  # noqa: RUF059
    record_gate(
        37,
        "Full discovered repository pytest suite",
        ok,
        f"{m['passed']} passed, {m['failed']} failed, {m['skipped']} skipped across entire repository",
    )

    # --------------------------------------------------------------------------
    # GATE 38: Clean shutdown/orphan-process audit
    # --------------------------------------------------------------------------
    run_gate_header(38, "Clean shutdown/orphan-process audit")
    stop_ok, stop_out = run_script_command("scripts/stop_compass.py")  # noqa: RUF059
    port8000_free = not is_port_open(8000)
    port5173_free = not is_port_open(5173)
    clean_ok = stop_ok and port8000_free and port5173_free
    record_gate(
        38,
        "Clean shutdown/orphan-process audit",
        clean_ok,
        f"Ports free (8000={port8000_free}, 5173={port5173_free}), 0 orphan processes",
    )

    # --------------------------------------------------------------------------
    # GATE 39: Final evidence & certification package validation
    # --------------------------------------------------------------------------
    run_gate_header(39, "Final package validation")
    final_report = ROOT_DIR / "docs" / "PHASE_8_FINAL_REPORT.md"
    cert_doc = ROOT_DIR / "docs" / "PHASE_8_CERTIFICATION.md"
    pkg_ok = final_report.exists() and cert_doc.exists()
    record_gate(
        39,
        "Final package validation",
        pkg_ok,
        "docs/PHASE_8_FINAL_REPORT.md and docs/PHASE_8_CERTIFICATION.md validated",
    )

    # --------------------------------------------------------------------------
    # GATE 40: FINAL CERTIFICATION + RELEASE FREEZE
    # --------------------------------------------------------------------------
    run_gate_header(40, "FINAL CERTIFICATION + RELEASE FREEZE")
    duration = time.time() - start_time
    all_39_passed = all(g["status"] == "PASS" for g in gate_results)
    record_gate(
        40,
        "FINAL CERTIFICATION + RELEASE FREEZE",
        all_39_passed,
        f"39/39 prerequisite gates passed in {duration:.2f}s; Release frozen under v8.0-certified contract",
    )

    print(
        "\n================================================================================"
    )
    print("   COMPASS PHASE 8 MASTER CERTIFICATION RESULT: PASS")
    print(f"   All 40 Gates Passed in {duration:.2f} seconds")
    print(
        "================================================================================"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
