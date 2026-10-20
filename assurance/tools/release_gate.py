"""
COMPASS Continuous Production Assurance — Release Gate Evaluator
Evaluates production-readiness across all assurance dimensions with fail-closed semantics.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

REPORT_DIR = ROOT_DIR / "assurance" / "reports"
FINDINGS_FILE = ROOT_DIR / "assurance" / "findings" / "finding_register.json"

MANDATORY_GATES = {
    "functional",
    "security",
    "sast",
    "dependency",
    "secret_scan",
    "api_security",
    "performance",
    "real_product",
}

# Justified Performance SLO Thresholds (ms)
PERFORMANCE_SLOS = {
    "planning_latency_ms": 2000.0,
    "stop_latency_ms": 500.0,
    "database_op_latency_ms": 100.0,
    "action_latency_ms": 250.0,
    "e2e_single_step_latency_ms": 1000.0,
    "replanning_latency_ms": 2000.0,
}


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def get_source_identity() -> dict[str, str]:
    """Retrieve git commit hash or calculate reproducible source identity hash."""
    commit_hash = "UNVERIFIED"
    try:
        r = subprocess.run(  # noqa: PLW1510
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ROOT_DIR),
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            commit_hash = r.stdout.strip()
    except Exception:  # noqa: BLE001
        pass

    # Source tree hash over core files
    h = hashlib.sha256()
    for root in ["backend", "planner", "automation", "perception", "assurance"]:
        dir_path = ROOT_DIR / root
        if dir_path.exists():
            for f in sorted(dir_path.glob("**/*.py")):
                try:
                    h.update(f.read_bytes())
                except Exception:
                    pass
    return {"commit_hash": commit_hash, "tree_hash": h.hexdigest()[:16]}


def evaluate_gate(run_id: str | None = None) -> dict:
    """
    Evaluate release-readiness gate from all available evidence.
    Fails closed: Any mandatory gate that is not PASS causes overall FAIL.
    """
    run_id = run_id or str(uuid.uuid4())
    source_id = get_source_identity()
    gates = {}

    # 1. Functional Gate: Phase 14 master report or master regression report
    p14_report = load_json(
        ROOT_DIR / "artifacts" / "phase14" / "phase14_master_report.json"
    )
    if p14_report and p14_report.get("overall_status") in ("PASS", "FAIL"):
        gates["functional"] = {
            "mandatory": True,
            "status": p14_report.get("overall_status"),
            "evidence": "artifacts/phase14/phase14_master_report.json",
            "stages_passed": sum(
                1 for s in p14_report.get("stages", []) if s.get("success")
            ),
            "stages_total": len(p14_report.get("stages", [])),
        }
    else:
        gates["functional"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "NOT FOUND or malformed",
        }

    # 2. Security Gate: Findings Register
    findings = []
    if FINDINGS_FILE.exists():
        try:
            findings = json.loads(FINDINGS_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    if findings:
        open_critical = [
            f
            for f in findings
            if f.get("severity") == "CRITICAL" and f.get("status") == "OPEN"
        ]
        open_high = [
            f
            for f in findings
            if f.get("severity") == "HIGH" and f.get("status") == "OPEN"
        ]
        status = "FAIL" if (open_critical or open_high) else "PASS"
        gates["security"] = {
            "mandatory": True,
            "status": status,
            "open_critical": len(open_critical),
            "open_high": len(open_high),
            "total_findings": len(findings),
            "evidence": "assurance/findings/finding_register.json",
        }
    else:
        gates["security"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "finding_register.json not found or empty",
        }

    # 3. SAST Gate (Bandit)
    sast = load_json(REPORT_DIR / "sast_report.json")
    if sast:
        bandit = sast.get("tools", {}).get("bandit", {})
        bandit_status = bandit.get("status")
        bandit_findings = bandit.get("total_findings", 0)
        gates["sast"] = {
            "mandatory": True,
            "status": "PASS"
            if bandit_status == "EXECUTED" and bandit_findings == 0
            else ("FAIL" if bandit_findings > 0 else "UNVERIFIED"),
            "findings_count": bandit_findings,
            "evidence": "assurance/reports/sast_report.json",
        }
    else:
        gates["sast"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "assurance/reports/sast_report.json not found",
        }

    # 4. Dependency Gate (pip-audit AND npm audit)
    dep = load_json(REPORT_DIR / "dependency_report.json")
    if dep:
        pip_vulns = (
            dep.get("tools", {}).get("pip_audit", {}).get("vulnerable_packages", 0)
        )
        npm_audit = dep.get("tools", {}).get("npm_audit", {})
        npm_vulns_summary = npm_audit.get("vulnerabilities_summary", {})
        npm_critical = npm_vulns_summary.get("critical", 0)
        npm_high = npm_vulns_summary.get("high", 0)

        dep_status = "PASS"
        if pip_vulns > 0 or npm_critical > 0 or npm_high > 0:
            dep_status = "FAIL"

        gates["dependency"] = {
            "mandatory": True,
            "status": dep_status,
            "pip_vulnerable_packages": pip_vulns,
            "npm_critical": npm_critical,
            "npm_high": npm_high,
            "evidence": "assurance/reports/dependency_report.json",
        }
    else:
        gates["dependency"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "assurance/reports/dependency_report.json not found",
        }

    # 5. Secret Scan Gate
    secret = load_json(REPORT_DIR / "secret_scan_report.json")
    if secret:
        secret_count = secret.get("total_findings", 0)
        gates["secret_scan"] = {
            "mandatory": True,
            "status": "FAIL" if secret_count > 0 else "PASS",
            "secrets_found": secret_count,
            "evidence": "assurance/reports/secret_scan_report.json",
        }
    else:
        gates["secret_scan"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "assurance/reports/secret_scan_report.json not found",
        }

    # 6. API Security Gate
    api = load_json(REPORT_DIR / "api_security_report.json")
    if api:
        if api.get("status") == "BLOCKED":
            gates["api_security"] = {
                "mandatory": True,
                "status": "BLOCKED",
                "reason": api.get("reason", "Server not running"),
                "evidence": "assurance/reports/api_security_report.json",
            }
        elif api.get("summary"):
            failed = api["summary"].get("failed", 0)
            gates["api_security"] = {
                "mandatory": True,
                "status": "FAIL" if failed > 0 else "PASS",
                "tests_passed": api["summary"].get("passed", 0),
                "tests_failed": failed,
                "evidence": "assurance/reports/api_security_report.json",
            }
        else:
            gates["api_security"] = {
                "mandatory": True,
                "status": "UNVERIFIED",
                "evidence": "api_security_report.json incomplete",
            }
    else:
        gates["api_security"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "assurance/reports/api_security_report.json not found",
        }

    # 7. Performance Gate: Evaluates actual benchmark metrics against justified SLO thresholds
    bench = load_json(ROOT_DIR / "artifacts" / "phase14" / "benchmark_comparison.json")
    if bench and "comparison" in bench:
        violations = []
        metrics_checked = {}
        for item in bench["comparison"]:
            m_name = item.get("metric")
            m_val = item.get("optimized", item.get("baseline", 0))
            metrics_checked[m_name] = m_val
            threshold = PERFORMANCE_SLOS.get(m_name)
            if threshold is not None and m_val > threshold:
                violations.append(f"{m_name}: {m_val}ms > {threshold}ms")

        perf_status = "FAIL" if violations else "PASS"
        gates["performance"] = {
            "mandatory": True,
            "status": perf_status,
            "violations": violations,
            "metrics": metrics_checked,
            "evidence": "artifacts/phase14/benchmark_comparison.json",
        }
    else:
        gates["performance"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "benchmark_comparison.json not found or malformed",
        }

    # 8. Real Assembled Product Gate
    real_prod = load_json(REPORT_DIR / "real_product_test_report.json")
    if real_prod:
        suites = real_prod.get("suites", {})
        total_real_tests = sum(len(tests) for tests in suites.values())
        failed_real_tests = sum(
            sum(1 for t in tests if not t.get("passed")) for tests in suites.values()
        )
        gates["real_product"] = {
            "mandatory": True,
            "status": "PASS"
            if total_real_tests > 0 and failed_real_tests == 0
            else "FAIL",
            "total_tests": total_real_tests,
            "failed_tests": failed_real_tests,
            "evidence": "assurance/reports/real_product_test_report.json",
        }
    else:
        gates["real_product"] = {
            "mandatory": True,
            "status": "UNVERIFIED",
            "evidence": "assurance/reports/real_product_test_report.json not found",
        }

    # 9. Git Cleanliness Gate (Optional / Advisory)
    try:
        r = subprocess.run(  # noqa: PLW1510
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(ROOT_DIR),
            timeout=5,
        )
        untracked = [l for l in r.stdout.strip().splitlines() if l.strip()]
        gates["git"] = {
            "mandatory": False,
            "status": "PASS" if not untracked else "WARN",
            "uncommitted_changes": len(untracked),
        }
    except Exception:  # noqa: BLE001
        gates["git"] = {"mandatory": False, "status": "UNVERIFIED"}

    # Overall readiness evaluation (FAIL CLOSED)
    # Any mandatory gate not strictly "PASS" blocks certification immediately.
    blocking_gates = [
        g
        for g, v in gates.items()
        if g in MANDATORY_GATES and v.get("status") != "PASS"
    ]
    warning_gates = [
        g
        for g, v in gates.items()
        if g not in MANDATORY_GATES and v.get("status") in ("WARN", "UNVERIFIED")
    ]

    overall = "FAIL" if blocking_gates else "PASS"

    result = {
        "run_id": run_id,
        "timestamp": time.time(),
        "source_identity": source_id,
        "overall_readiness": overall,
        "blocking_gates": blocking_gates,
        "warning_gates": warning_gates,
        "mandatory_gates_count": len(MANDATORY_GATES),
        "gates": gates,
    }

    out = REPORT_DIR / "release_gate_report.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = evaluate_gate()
    print(f"\nRelease Readiness: [{result['overall_readiness']}]")
    if result["blocking_gates"]:
        print(f"  Blocking: {', '.join(result['blocking_gates'])}")
    if result["warning_gates"]:
        print(f"  Warnings: {', '.join(result['warning_gates'])}")

    # FAIL-CLOSED EXIT CODE: Non-zero exit when certification is not PASS
    sys.exit(0 if result["overall_readiness"] == "PASS" else 1)
