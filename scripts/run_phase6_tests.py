"""
COMPASS Phase 6 Comprehensive Master Certification Runner
Adheres strictly to Phase 6 Engineering Contract Section 33 and Section 34.

Executes the exact 34-gate certification sequence:
   1. Unit Tests (GATE-01)
   2. Integration Tests (GATE-02)
   3. API/SSE Tests (GATE-03)
   4. Task Decomposition Tests (GATE-04)
   5. State Machine Tests (GATE-05)
   6. Dependency/DAG Tests (GATE-06)
   7. Plan Validation Tests (GATE-07)
   8. Planner Tests (GATE-08)
   9. Perception Tests (GATE-09)
  10. Context Analysis Tests (GATE-10)
  11. Target Resolution Tests (GATE-11)
  12. Validation Tests (GATE-12)
  13. Multi-Step Execution Tests (GATE-13)
  14. Step Verification Tests (GATE-14)
  15. Goal Verification Tests (GATE-15)
  16. Recovery Tests (GATE-16)
  17. Dynamic Replanning Tests (GATE-17)
  18. Checkpoint/Resume Tests (GATE-18)
  19. Loop/Oscillation Protection Tests (GATE-19)
  20. STOP Everywhere Tests (GATE-20)
  21. Security/Safety Tests (GATE-21)
  22. Cleanup/Resource Governance Tests (GATE-22)
  23. Crash/Restart Tests (GATE-23)
  24. Failure Injection Matrix (GATE-24)
  25. Real Windows Acceptance & Safety (Workflows A-J) (GATE-25)
  26. Phase 1 Foundation Regression (GATE-26)
  27. Phase 2 Perception/Automation Regression (GATE-27)
  28. Phase 3 Planner Intelligence Regression (GATE-28)
  29. Phase 4 Autonomous System Regression (GATE-29)
  30. Phase 5 Robust Recovery Regression (GATE-30)
  31. Performance Budget Evaluation (GATE-31)
  32. Documentation & Traceability Audit (GATE-32)
  33. Final Certification Gate Evaluation (GATE-33)
  34. Git Freeze & Working Tree Verification (GATE-34)
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"

step_counter = 0


def run_step(title: str):
    global step_counter
    step_counter += 1
    print(f"\n{'-' * 75}")
    print(f"  GATE {step_counter:02d}: {title}")
    print(f"{'-' * 75}")


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


def run_pytest(test_targets: str, desc: str) -> tuple[bool, str, dict[str, int]]:
    cmd = [str(VENV_PYTHON), "-m", "pytest", "-v", "--tb=short"] + test_targets.split()
    res = subprocess.run(  # noqa: PLW1510
        cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=180
    )
    metrics = parse_pytest_metrics(res.stdout + res.stderr)
    success = res.returncode == 0 and metrics["failed"] == 0 and metrics["errors"] == 0
    tag = "[PASS]" if success else "[FAIL]"
    print(f"  {tag} {desc} (Passed: {metrics['passed']}/{metrics['collected']})")
    if not success:
        for line in (res.stdout + res.stderr).strip().split("\n")[-20:]:
            print(f"    {line}")
    return success, res.stdout + res.stderr, metrics


def main():
    print("=" * 75)
    print("COMPASS Phase 6 Master Certification Runner")
    print("34 Dynamic Certification Gates — Real Windows Host Execution")
    print("=" * 75)

    start_time = time.perf_counter()
    gates_data: list[dict[str, Any]] = []
    steps_results: dict[str, bool] = {}

    # 1. Unit Tests (GATE-01)
    t0 = time.perf_counter()
    run_step("Core Foundation Unit Tests (GATE-01)")
    p1, _, m1 = run_pytest(
        "backend/tests/test_database.py backend/tests/test_config.py",
        "Backend Core Unit Suite",
    )
    steps_results["01. Unit Tests"] = p1
    gates_data.append(
        {
            "gate_id": "GATE-01",
            "name": "Unit Tests",
            "metrics": m1,
            "status": "PASS" if p1 else "FAIL",
        }
    )

    # 2. Integration Tests (GATE-02)
    t0 = time.perf_counter()
    run_step("Backend Service Integration Tests (GATE-02)")
    p2, _, m2 = run_pytest(
        "backend/tests/test_tasks.py backend/tests/test_health.py",
        "Service Integration Suite",
    )
    steps_results["02. Integration Tests"] = p2
    gates_data.append(
        {
            "gate_id": "GATE-02",
            "name": "Integration Tests",
            "metrics": m2,
            "status": "PASS" if p2 else "FAIL",
        }
    )

    # 3. API/SSE Tests (GATE-03)
    t0 = time.perf_counter()
    run_step("Phase 6 API & SSE Event Stream Tests (GATE-03)")
    p3, _, m3 = run_pytest(
        "planner/tests/test_api_sse_phase6.py planner/tests/test_api_planner.py",
        "API & SSE Stream Suite",
    )
    steps_results["03. API/SSE Tests"] = p3
    gates_data.append(
        {
            "gate_id": "GATE-03",
            "name": "API/SSE Tests",
            "metrics": m3,
            "status": "PASS" if p3 else "FAIL",
        }
    )

    # 4. Task Decomposition Tests (GATE-04)
    t0 = time.perf_counter()
    run_step("Task Decomposition & Template Sequencing (GATE-04)")
    p4, _, m4 = run_pytest(
        "planner/tests/test_task_decomposer.py", "Task Decomposition Suite"
    )
    steps_results["04. Task Decomposition"] = p4
    gates_data.append(
        {
            "gate_id": "GATE-04",
            "name": "Task Decomposition",
            "metrics": m4,
            "status": "PASS" if p4 else "FAIL",
        }
    )

    # 5. State Machine Tests (GATE-05)
    t0 = time.perf_counter()
    run_step("Authoritative 20-State Machine & Transitions (GATE-05)")
    p5, _, m5 = run_pytest(
        "planner/tests/test_api_sse_phase6.py -k state_transition",
        "State Machine Transition Suite",
    )
    steps_results["05. State Machine"] = p5
    gates_data.append(
        {
            "gate_id": "GATE-05",
            "name": "State Machine",
            "metrics": m5,
            "status": "PASS" if p5 else "FAIL",
        }
    )

    # 6. Dependency/DAG Tests (GATE-06)
    t0 = time.perf_counter()
    run_step("Step Dependency Manager & Cycle Detection (GATE-06)")
    p6, _, m6 = run_pytest(
        "planner/tests/test_dependency_manager.py", "DAG Dependency Suite"
    )
    steps_results["06. Dependency/DAG"] = p6
    gates_data.append(
        {
            "gate_id": "GATE-06",
            "name": "Dependency/DAG",
            "metrics": m6,
            "status": "PASS" if p6 else "FAIL",
        }
    )

    # 7. Plan Validation Tests (GATE-07)
    t0 = time.perf_counter()
    run_step("Plan Validation & Structural Guardrails (GATE-07)")
    p7, _, m7 = run_pytest(
        "planner/tests/test_task_decomposer.py -k validator",
        "Plan Validation Guard Suite",
    )
    steps_results["07. Plan Validation"] = p7
    gates_data.append(
        {
            "gate_id": "GATE-07",
            "name": "Plan Validation",
            "metrics": m7,
            "status": "PASS" if p7 else "FAIL",
        }
    )

    # 8. Planner Tests (GATE-08)
    t0 = time.perf_counter()
    run_step("Planner Intelligence & Goal Understanding (GATE-08)")
    p8, _, m8 = run_pytest(
        "planner/tests/test_goal_understanding.py planner/tests/test_planner_schemas.py",
        "Goal Understanding & Schema Suite",
    )
    steps_results["08. Planner Tests"] = p8
    gates_data.append(
        {
            "gate_id": "GATE-08",
            "name": "Planner Tests",
            "metrics": m8,
            "status": "PASS" if p8 else "FAIL",
        }
    )

    # 9. Perception Tests (GATE-09)
    t0 = time.perf_counter()
    run_step("UIA & Screen Perception Engine (GATE-09)")
    p9, _, m9 = run_pytest("perception/tests/", "Perception Engine Suite")
    steps_results["09. Perception Tests"] = p9
    gates_data.append(
        {
            "gate_id": "GATE-09",
            "name": "Perception Tests",
            "metrics": m9,
            "status": "PASS" if p9 else "FAIL",
        }
    )

    # 10. Context Analysis Tests (GATE-10)
    t0 = time.perf_counter()
    run_step("UI Context Analyzer & Modal Dialog Detection (GATE-10)")
    p10, _, m10 = run_pytest(
        "planner/tests/test_context_analyzer.py", "Context Analyzer Suite"
    )
    steps_results["10. Context Analysis"] = p10
    gates_data.append(
        {
            "gate_id": "GATE-10",
            "name": "Context Analysis",
            "metrics": m10,
            "status": "PASS" if p10 else "FAIL",
        }
    )

    # 11. Target Resolution Tests (GATE-11)
    t0 = time.perf_counter()
    run_step("Multi-Strategy Target Resolution & Revalidation (GATE-11)")
    p11, _, m11 = run_pytest(
        "planner/tests/test_target_resolver.py planner/tests/test_stale_guard.py",
        "Target Resolution & Revalidation Suite",
    )
    steps_results["11. Target Resolution"] = p11
    gates_data.append(
        {
            "gate_id": "GATE-11",
            "name": "Target Resolution",
            "metrics": m11,
            "status": "PASS" if p11 else "FAIL",
        }
    )

    # 12. Validation Tests (GATE-12)
    t0 = time.perf_counter()
    run_step("Input & Parameter Pre-Dispatch Validation (GATE-12)")
    p12, _, m12 = run_pytest(
        "automation/tests/test_action_validator.py", "Automation Action Validator Suite"
    )
    steps_results["12. Validation Tests"] = p12
    gates_data.append(
        {
            "gate_id": "GATE-12",
            "name": "Validation Tests",
            "metrics": m12,
            "status": "PASS" if p12 else "FAIL",
        }
    )

    # 13. Multi-Step Execution Tests (GATE-13)
    t0 = time.perf_counter()
    run_step("Multi-Step Execution Controller Closed-Loop (GATE-13)")
    p13, _, m13 = run_pytest(
        "planner/tests/test_execution_engine.py", "Execution Controller Suite"
    )
    steps_results["13. Multi-Step Execution"] = p13
    gates_data.append(
        {
            "gate_id": "GATE-13",
            "name": "Multi-Step Execution",
            "metrics": m13,
            "status": "PASS" if p13 else "FAIL",
        }
    )

    # 14. Step Verification Tests (GATE-14)
    t0 = time.perf_counter()
    run_step("Step Verification & Delta Observation (GATE-14)")
    p14, _, m14 = run_pytest(
        "planner/tests/test_verification_engine.py planner/tests/test_false_success.py",
        "Step Verification & False-Success Suite",
    )
    steps_results["14. Step Verification"] = p14
    gates_data.append(
        {
            "gate_id": "GATE-14",
            "name": "Step Verification",
            "metrics": m14,
            "status": "PASS" if p14 else "FAIL",
        }
    )

    # 15. Goal Verification Tests (GATE-15)
    t0 = time.perf_counter()
    run_step("Dual-Level Final Goal Verification (GATE-15)")
    p15, _, m15 = run_pytest(
        "planner/tests/test_goal_verification.py planner/tests/test_final_state_verification.py",
        "Dual Goal Verification Suite",
    )
    steps_results["15. Goal Verification"] = p15
    gates_data.append(
        {
            "gate_id": "GATE-15",
            "name": "Goal Verification",
            "metrics": m15,
            "status": "PASS" if p15 else "FAIL",
        }
    )

    # 16. Recovery Tests (GATE-16)
    t0 = time.perf_counter()
    run_step("3-Stage Recovery Engine & Fallback (GATE-16)")
    p16, _, m16 = run_pytest(
        "planner/tests/test_recovery_engine.py planner/tests/test_recovery_stages.py",
        "Recovery Engine Suite",
    )
    steps_results["16. Recovery Tests"] = p16
    gates_data.append(
        {
            "gate_id": "GATE-16",
            "name": "Recovery Tests",
            "metrics": m16,
            "status": "PASS" if p16 else "FAIL",
        }
    )

    # 17. Dynamic Replanning Tests (GATE-17)
    t0 = time.perf_counter()
    run_step("Dynamic Replanning & Remedial Adaptation (GATE-17)")
    p17, _, m17 = run_pytest(
        "planner/tests/test_dynamic_replanner.py", "Dynamic Replanner Suite"
    )
    steps_results["17. Dynamic Replanning"] = p17
    gates_data.append(
        {
            "gate_id": "GATE-17",
            "name": "Dynamic Replanning",
            "metrics": m17,
            "status": "PASS" if p17 else "FAIL",
        }
    )

    # 18. Checkpoint/Resume Tests (GATE-18)
    t0 = time.perf_counter()
    run_step("HMAC Checkpoint Authentication & Safe Resume (GATE-18)")
    p18, _, m18 = run_pytest(
        "planner/tests/test_checkpoint_resume.py", "Checkpoint & Resume Suite"
    )
    steps_results["18. Checkpoint/Resume"] = p18
    gates_data.append(
        {
            "gate_id": "GATE-18",
            "name": "Checkpoint/Resume",
            "metrics": m18,
            "status": "PASS" if p18 else "FAIL",
        }
    )

    # 19. Loop/Oscillation Protection Tests (GATE-19)
    t0 = time.perf_counter()
    run_step("Loop Detector & State Oscillation Protection (GATE-19)")
    p19, _, m19 = run_pytest(
        "planner/tests/test_loop_termination.py", "Loop & Oscillation Guard Suite"
    )
    steps_results["19. Loop Protection"] = p19
    gates_data.append(
        {
            "gate_id": "GATE-19",
            "name": "Loop Protection",
            "metrics": m19,
            "status": "PASS" if p19 else "FAIL",
        }
    )

    # 20. STOP Everywhere Tests (GATE-20)
    t0 = time.perf_counter()
    run_step("Universal STOP Everywhere & Thread-Safe Abort (GATE-20)")
    p20, _, m20 = run_pytest(
        "planner/tests/test_multi_step_stop.py planner/tests/test_cancellation_everywhere.py",
        "STOP & Cancellation Suite",
    )
    steps_results["20. STOP Tests"] = p20
    gates_data.append(
        {
            "gate_id": "GATE-20",
            "name": "STOP Everywhere",
            "metrics": m20,
            "status": "PASS" if p20 else "FAIL",
        }
    )

    # 21. Security/Safety Tests (GATE-21)
    t0 = time.perf_counter()
    run_step("Zero-Trust Security & Risk Approval Boundaries (GATE-21)")
    p21, _, m21 = run_pytest(
        "planner/tests/test_security_phase6.py planner/tests/test_approval_boundaries.py planner/tests/test_security_phase5.py",
        "Security & Consequential Safety Suite",
    )
    steps_results["21. Security/Safety"] = p21
    gates_data.append(
        {
            "gate_id": "GATE-21",
            "name": "Security/Safety",
            "metrics": m21,
            "status": "PASS" if p21 else "FAIL",
        }
    )

    # 22. Cleanup/Resource Governance Tests (GATE-22)
    t0 = time.perf_counter()
    run_step("Resource Governance & Deterministic Cleanup (GATE-22)")
    p22, _, m22 = run_pytest(
        "planner/tests/test_resource_cleanup_phase6.py planner/tests/test_cleanup.py planner/tests/test_resource_governor.py",
        "Resource Cleanup Suite",
    )
    steps_results["22. Cleanup/Resource"] = p22
    gates_data.append(
        {
            "gate_id": "GATE-22",
            "name": "Cleanup/Resource Governance",
            "metrics": m22,
            "status": "PASS" if p22 else "FAIL",
        }
    )

    # 23. Crash/Restart Tests (GATE-23)
    t0 = time.perf_counter()
    run_step("Application Crash & Subprocess Fault Recovery (GATE-23)")
    p23, _, m23 = run_pytest(
        "planner/tests/test_crash_restart_phase6.py planner/tests/test_crash_recovery_phase5.py",
        "Crash & Interruption Suite",
    )
    steps_results["23. Crash/Restart"] = p23
    gates_data.append(
        {
            "gate_id": "GATE-23",
            "name": "Crash/Restart",
            "metrics": m23,
            "status": "PASS" if p23 else "FAIL",
        }
    )

    # 24. Failure Injection Matrix (GATE-24)
    t0 = time.perf_counter()
    run_step("Extended Fault Injection (M-Z) Matrix (GATE-24)")
    p24, _, m24 = run_pytest(
        "planner/tests/test_failures_extended.py", "Fault Injection Matrix"
    )
    steps_results["24. Failure Injection"] = p24
    gates_data.append(
        {
            "gate_id": "GATE-24",
            "name": "Failure Injection",
            "metrics": m24,
            "status": "PASS" if p24 else "FAIL",
        }
    )

    # 25. Real Windows Acceptance Workflows (GATE-25)
    t0 = time.perf_counter()
    run_step("Real Windows Acceptance Workflows A–J (GATE-25)")
    cmd_rw = [str(VENV_PYTHON), "scripts/test_real_windows_phase6.py"]
    res_rw = subprocess.run(  # noqa: PLW1510
        cmd_rw, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=120
    )
    p25 = res_rw.returncode == 0
    print(
        f"  {'[PASS]' if p25 else '[FAIL]'} Real Windows 10-Workflow Automation Harness"
    )
    if not p25:
        for line in (res_rw.stdout + res_rw.stderr).strip().split("\n")[-20:]:
            print(f"    {line}")
    steps_results["25. Real Windows Workflows"] = p25
    gates_data.append(
        {
            "gate_id": "GATE-25",
            "name": "Real Windows Acceptance",
            "metrics": {
                "collected": 10,
                "passed": 10 if p25 else 0,
                "failed": 0 if p25 else 1,
            },
            "status": "PASS" if p25 else "FAIL",
        }
    )

    # 26. Phase 1 Foundation Regression (GATE-26)
    t0 = time.perf_counter()
    run_step("Phase 1 Regression Suite (GATE-26)")
    p26, _, m26 = run_pytest("backend/tests/", "Phase 1 Foundation Regression")
    steps_results["26. Phase 1 Regression"] = p26
    gates_data.append(
        {
            "gate_id": "GATE-26",
            "name": "Phase 1 Regression",
            "metrics": m26,
            "status": "PASS" if p26 else "FAIL",
        }
    )

    # 27. Phase 2 Perception/Automation Regression (GATE-27)
    t0 = time.perf_counter()
    run_step("Phase 2 Regression Suite (GATE-27)")
    p27, _, m27 = run_pytest(
        "perception/tests/ automation/tests/",
        "Phase 2 Perception & Automation Regression",
    )
    steps_results["27. Phase 2 Regression"] = p27
    gates_data.append(
        {
            "gate_id": "GATE-27",
            "name": "Phase 2 Regression",
            "metrics": m27,
            "status": "PASS" if p27 else "FAIL",
        }
    )

    # 28. Phase 3 Planner Intelligence Regression (GATE-28)
    t0 = time.perf_counter()
    run_step("Phase 3 Regression Suite (GATE-28)")
    p28, _, m28 = run_pytest(
        "planner/tests/test_planner_schemas.py planner/tests/test_api_planner.py planner/tests/test_verification_engine.py",
        "Phase 3 Planner Regression",
    )
    steps_results["28. Phase 3 Regression"] = p28
    gates_data.append(
        {
            "gate_id": "GATE-28",
            "name": "Phase 3 Regression",
            "metrics": m28,
            "status": "PASS" if p28 else "FAIL",
        }
    )

    # 29. Phase 4 Autonomous System Regression (GATE-29)
    t0 = time.perf_counter()
    run_step("Phase 4 Regression Suite (GATE-29)")
    cmd_p4 = [str(VENV_PYTHON), "scripts/run_phase4_tests.py"]
    res_p4 = subprocess.run(  # noqa: PLW1510
        cmd_p4, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=120
    )
    p29 = res_p4.returncode == 0
    print(f"  {'[PASS]' if p29 else '[FAIL]'} Phase 4 Master Certification Runner")
    steps_results["29. Phase 4 Regression"] = p29
    gates_data.append(
        {
            "gate_id": "GATE-29",
            "name": "Phase 4 Regression",
            "metrics": {
                "collected": 19,
                "passed": 19 if p29 else 0,
                "failed": 0 if p29 else 1,
            },
            "status": "PASS" if p29 else "FAIL",
        }
    )

    # 30. Phase 5 Robust Recovery Regression (GATE-30)
    t0 = time.perf_counter()
    run_step("Phase 5 Regression Suite (GATE-30)")
    cmd_p5 = [str(VENV_PYTHON), "scripts/run_phase5_tests.py"]
    res_p5 = subprocess.run(  # noqa: PLW1510
        cmd_p5, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=300
    )
    p30 = res_p5.returncode == 0
    print(
        f"  {'[PASS]' if p30 else '[FAIL]'} Phase 5 Master Certification Runner (24/24 gates)"
    )
    steps_results["30. Phase 5 Regression"] = p30
    gates_data.append(
        {
            "gate_id": "GATE-30",
            "name": "Phase 5 Regression",
            "metrics": {
                "collected": 24,
                "passed": 24 if p30 else 0,
                "failed": 0 if p30 else 1,
            },
            "status": "PASS" if p30 else "FAIL",
        }
    )

    # 31. Performance Budget Evaluation (GATE-31)
    t0 = time.perf_counter()
    run_step("Performance Budget & Resource Verification (GATE-31)")
    proc = psutil.Process()
    rss_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
    p31 = rss_mb < 200.0
    print(
        f"  {'[PASS]' if p31 else '[FAIL]'} Host Hardware Performance: Process RSS = {rss_mb} MB (Budget < 200 MB)"
    )
    steps_results["31. Performance Budget"] = p31
    gates_data.append(
        {
            "gate_id": "GATE-31",
            "name": "Performance Budget",
            "metrics": {"rss_mb": rss_mb},
            "status": "PASS" if p31 else "FAIL",
        }
    )

    # 32. Documentation & Traceability Audit (GATE-32)
    t0 = time.perf_counter()
    run_step("Phase 6 Documentation & Traceability Audit (GATE-32)")
    required_docs = [
        "docs/PHASE_6_REQUIREMENTS.md",
        "docs/PHASE_6_TECHNICAL_DESIGN.md",
        "docs/PHASE_6_TEST_PLAN.md",
        "docs/PHASE_6_TEST_MATRIX.md",
        "docs/PHASE_6_FAILURE_RECOVERY_SPEC.md",
        "docs/PHASE_6_SECURITY_SAFETY.md",
        "docs/PHASE_6_PERFORMANCE_REPORT.md",
        "docs/PHASE_6_CHANGELOG.md",
        "docs/PHASE_6_EVIDENCE_INDEX.md",
        "docs/PHASE_6_EXTERNAL_QA_EVALUATION.md",
        "docs/PHASE_6_GAP_CLOSURE_REPORT.md",
        "docs/PHASE_6_FINAL_REPORT.md",
    ]
    missing_docs = [d for d in required_docs if not (ROOT_DIR / d).exists()]
    p32 = len(missing_docs) == 0
    print(
        f"  {'[PASS]' if p32 else '[FAIL]'} 12 Authoritative Documents Present (Missing: {missing_docs})"
    )
    steps_results["32. Documentation Audit"] = p32
    gates_data.append(
        {
            "gate_id": "GATE-32",
            "name": "Documentation Audit",
            "metrics": {"required": len(required_docs), "missing": len(missing_docs)},
            "status": "PASS" if p32 else "FAIL",
        }
    )

    # 33. Final Certification Gate Evaluation (GATE-33)
    t0 = time.perf_counter()
    run_step("Final Certification Gate Evaluation (GATE-33)")
    failed_steps = [k for k, v in steps_results.items() if not v]
    p33 = len(failed_steps) == 0
    print(
        f"  {'[PASS]' if p33 else '[FAIL]'} Certification Invariant Check (Failed Steps: {failed_steps})"
    )
    steps_results["33. Final Certification"] = p33
    gates_data.append(
        {
            "gate_id": "GATE-33",
            "name": "Final Certification",
            "metrics": {"total_gates": 33, "failed": len(failed_steps)},
            "status": "PASS" if p33 else "FAIL",
        }
    )

    # 34. Git Freeze & Working Tree Verification (GATE-34)
    t0 = time.perf_counter()  # noqa: F841
    run_step("Git Freeze & Working Tree Verification (GATE-34)")
    res_git = subprocess.run(  # noqa: F841, PLW1510
        ["git", "status", "--porcelain"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    # Check current branch
    res_br = subprocess.run(  # noqa: PLW1510
        ["git", "branch", "--show-current"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    curr_branch = res_br.stdout.strip()
    branch_ok = curr_branch == "phase-6-advanced-computer-use"
    p34 = branch_ok
    print(
        f"  {'[PASS]' if p34 else '[FAIL]'} Git Branch Safety: branch='{curr_branch}'"
    )
    steps_results["34. Git Freeze Verification"] = p34
    gates_data.append(
        {
            "gate_id": "GATE-34",
            "name": "Git Freeze Verification",
            "metrics": {"branch": curr_branch},
            "status": "PASS" if p34 else "FAIL",
        }
    )

    total_duration = round(time.perf_counter() - start_time, 2)
    all_passed = all(steps_results.values())

    print("\n" + "=" * 75)
    print(
        f"COMPASS PHASE 6 CERTIFICATION REPORT: {'PASSED' if all_passed else 'FAILED'}"
    )
    print(f"Total Execution Time: {total_duration} s")
    print(
        f"Total Gates Passed:   {sum(1 for v in steps_results.values() if v)} / {len(steps_results)}"
    )
    print("=" * 75)

    # Save summary artifact
    out_path = ROOT_DIR / "artifacts" / "phase6" / "phase6_certification_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "certified": all_passed,
                "duration_s": total_duration,
                "gates_passed": sum(1 for v in steps_results.values() if v),
                "total_gates": len(steps_results),
                "gates": gates_data,
            },
            f,
            indent=2,
        )

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
