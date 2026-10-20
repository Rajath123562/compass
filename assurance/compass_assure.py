"""
COMPASS Continuous Production Assurance — Master Runner
Orchestrates the complete assurance pipeline:

  INVENTORY → STATIC → DEPENDENCY → SECRET → API → REGRESSION → ADVERSARIAL →
  REAL WINDOWS → PERFORMANCE → RELEASE GATE → REPORT

Usage:
  python assurance/compass_assure.py                    # Full assurance run
  python assurance/compass_assure.py --quick             # Inventory + Static + Secret + Regression
  python assurance/compass_assure.py --security          # Static + Dependency + Secret + API
  python assurance/compass_assure.py --runtime           # API + Real Windows + Adversarial
  python assurance/compass_assure.py --regression        # Pytest regression only
  python assurance/compass_assure.py --performance       # Benchmark comparison only
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

PYTHON_EXE = (
    str(ROOT_DIR / ".venv" / "Scripts" / "python.exe")
    if (ROOT_DIR / ".venv" / "Scripts" / "python.exe").exists()
    else sys.executable
)
REPORT_DIR = ROOT_DIR / "assurance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR = ROOT_DIR / "assurance" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


class AssuranceRunner:
    def __init__(self, mode: str = "full"):
        self.mode = mode
        self.results = {
            "timestamp": datetime.now().isoformat(),  # noqa: DTZ005
            "mode": mode,
            "environment": self._collect_environment(),
            "stages": {},
            "summary": {},
        }
        self.stage_count = 0
        self.passed = 0
        self.failed = 0
        self.blocked = 0
        self.skipped = 0

    def _collect_environment(self) -> dict:
        vm = psutil.virtual_memory()
        return {
            "os": f"{platform.system()} {platform.release()} (Build {platform.version()})",
            "python": platform.python_version(),
            "cpu": platform.processor(),
            "ram_total_gb": round(vm.total / (1024**3), 2),
            "ram_available_gb": round(vm.available / (1024**3), 2),
        }

    def _run_stage(
        self, name: str, description: str, cmd: list, timeout: int = 300
    ) -> dict:
        """Execute a single assurance stage."""
        self.stage_count += 1
        stage_num = self.stage_count
        print(f"\n{'=' * 80}")
        print(f"  Stage {stage_num}: {description}")
        print(f"{'=' * 80}")

        t0 = time.time()
        try:
            proc = subprocess.run(  # noqa: PLW1510
                cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=timeout
            )
            duration = round(time.time() - t0, 2)
            success = proc.returncode == 0
            status = "PASS" if success else "FAIL"

            if proc.stdout:
                lines = proc.stdout.strip().splitlines()
                for line in lines[-8:]:
                    print(f"    | {line}")

            if not success and proc.stderr:
                for line in proc.stderr.strip().splitlines()[-5:]:
                    print(f"    ! {line}")

            if success:
                self.passed += 1
            else:
                self.failed += 1

            print(f"  [{status}] in {duration}s")
            return {
                "stage": stage_num,
                "name": name,
                "description": description,
                "status": status,
                "duration_s": duration,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-3000:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
            }
        except subprocess.TimeoutExpired:
            duration = round(time.time() - t0, 2)
            self.blocked += 1
            print(f"  [TIMEOUT] after {duration}s")
            return {
                "stage": stage_num,
                "name": name,
                "status": "TIMEOUT",
                "duration_s": duration,
            }
        except Exception as e:  # noqa: BLE001
            duration = round(time.time() - t0, 2)
            self.failed += 1
            print(f"  [ERROR] {e}")
            return {
                "stage": stage_num,
                "name": name,
                "status": "ERROR",
                "duration_s": duration,
                "error": str(e),
            }

    def _should_run(self, stage_key: str) -> bool:
        """Determine if a stage should run based on the mode."""
        mode_map = {
            "full": True,
            "quick": stage_key in ("inventory", "sast", "secret", "regression"),
            "security": stage_key
            in ("inventory", "sast", "dependency", "secret", "api"),
            "runtime": stage_key
            in ("api", "adversarial", "real_windows", "real_product"),
            "real_product": stage_key in ("real_product",),
            "regression": stage_key in ("regression",),
            "performance": stage_key in ("performance",),
        }
        return mode_map.get(self.mode, True)

    def run(self):
        """Execute the complete assurance pipeline for the selected mode."""
        print("=" * 80)
        print(f"  COMPASS CONTINUOUS PRODUCTION ASSURANCE — Mode: {self.mode.upper()}")
        print(f"  Timestamp: {self.results['timestamp']}")
        print(f"  Environment: {self.results['environment']['os']}")
        print("=" * 80)

        t_start = time.time()

        # Stage 1: Application Inventory
        if self._should_run("inventory"):
            r = self._run_stage(
                "inventory",
                "Application Inventory & Attack Surface Discovery",
                [PYTHON_EXE, "assurance/inventory_builder.py"],
            )
            self.results["stages"]["inventory"] = r

        # Stage 2: Static Analysis (SAST)
        if self._should_run("sast"):
            r = self._run_stage(
                "sast",
                "Static Application Security Testing (Bandit)",
                [PYTHON_EXE, "assurance/tools/sast_runner.py"],
                timeout=180,
            )
            self.results["stages"]["sast"] = r

        # Stage 3: Dependency Security
        if self._should_run("dependency"):
            r = self._run_stage(
                "dependency",
                "Dependency Vulnerability Scanning (pip-audit + npm audit)",
                [PYTHON_EXE, "assurance/tools/dependency_scanner.py"],
                timeout=180,
            )
            self.results["stages"]["dependency"] = r

        # Stage 4: Secret Scanning
        if self._should_run("secret"):
            r = self._run_stage(
                "secret",
                "Secret & Credential Leakage Scanning",
                [PYTHON_EXE, "assurance/tools/secret_scanner.py"],
            )
            self.results["stages"]["secret"] = r

        # Stage 5: Existing Phase Secrets Audit
        if self._should_run("secret"):
            r = self._run_stage(
                "legacy_secret_audit",
                "Phase 1-14 Legacy Secret Audit",
                [PYTHON_EXE, "scripts/audit_security_secrets.py"],
            )
            self.results["stages"]["legacy_secret_audit"] = r

        # Stage 6: Full Pytest Regression
        if self._should_run("regression"):
            r = self._run_stage(
                "regression",
                "Full Multi-Phase Pytest Regression Suite (808 tests)",
                [PYTHON_EXE, "-m", "pytest", "-q", "--tb=short"],
                timeout=600,
            )
            self.results["stages"]["regression"] = r

        # Stage 7: Phase 13 Adversarial Pytest
        if self._should_run("adversarial"):
            r = self._run_stage(
                "adversarial_pytest",
                "Phase 13 Adversarial Pytest Suite (15 attacks)",
                [
                    PYTHON_EXE,
                    "-m",
                    "pytest",
                    "planner/tests/test_phase13_adversarial.py",
                    "-v",
                    "--tb=short",
                ],
            )
            self.results["stages"]["adversarial_pytest"] = r

        # Stage 8: Live Windows Adversarial Campaign
        if self._should_run("adversarial"):
            r = self._run_stage(
                "adversarial_live",
                "Live Windows 11 Adversarial Attack Campaign (20 attacks)",
                [PYTHON_EXE, "scripts/test_adversarial_phase13.py"],
                timeout=180,
            )
            self.results["stages"]["adversarial_live"] = r

        # Stage 9: Real Windows Desktop Workflows
        if self._should_run("real_windows"):
            r = self._run_stage(
                "real_windows",
                "Real Windows Desktop Acceptance Workflows (24 workflows A-X)",
                [PYTHON_EXE, "scripts/test_real_windows_phase12.py"],
                timeout=180,
            )
            self.results["stages"]["real_windows"] = r

        # Stage 9.5: Real Assembled Product Verification Suite
        if self._should_run("real_product"):
            r = self._run_stage(
                "real_product",
                "Assembled COMPASS Product E2E Verification (Backend+Frontend+Windows)",
                [PYTHON_EXE, "assurance/real_product_suite.py"],
                timeout=300,
            )
            self.results["stages"]["real_product"] = r

        # Stage 10: Hardware Stability
        if self._should_run("performance"):
            r = self._run_stage(
                "stability",
                "Hardware Stability & Memory Bounds Verification (25 cycles)",
                [PYTHON_EXE, "scripts/test_stability_phase10.py"],
                timeout=180,
            )
            self.results["stages"]["stability"] = r

        # Stage 11: Performance Benchmark
        if self._should_run("performance"):
            r = self._run_stage(
                "performance",
                "Phase 14 Performance Benchmark (Optimized Mode)",
                [PYTHON_EXE, "scripts/benchmark_phase14.py", "--mode", "optimized"],
                timeout=180,
            )
            self.results["stages"]["performance"] = r

        # Stage 12: API Security Testing (requires running server)
        if self._should_run("api"):
            r = self._run_stage(
                "api_security",
                "API Security & Fuzz Testing (against live server)",
                [PYTHON_EXE, "assurance/tools/api_security_tester.py"],
                timeout=120,
            )
            self.results["stages"]["api_security"] = r

        # Stage 13: Release Gate
        r = self._run_stage(
            "release_gate",
            "Production Release Gate Evaluation",
            [PYTHON_EXE, "assurance/tools/release_gate.py"],
        )
        gate_rep_path = REPORT_DIR / "release_gate_report.json"
        if gate_rep_path.exists():
            try:
                gate_json = json.loads(gate_rep_path.read_text(encoding="utf-8"))
                if gate_json.get("overall_readiness") != "PASS":
                    if r.get("status") == "PASS":
                        r["status"] = "FAIL"
                        self.passed -= 1
                        self.failed += 1
            except Exception:
                pass
        self.results["stages"]["release_gate"] = r

        # Build Summary
        total_duration = round(time.time() - t_start, 2)
        self.results["summary"] = {
            "total_stages": self.stage_count,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "total_duration_s": total_duration,
            "overall_status": "PASS"
            if self.failed == 0 and self.blocked == 0
            else "FAIL",
        }

        # Load findings summary
        findings_file = ROOT_DIR / "assurance" / "findings" / "finding_register.json"
        if findings_file.exists():
            try:
                findings = json.loads(findings_file.read_text(encoding="utf-8"))
                self.results["summary"]["total_findings"] = len(findings)
                self.results["summary"]["open_findings"] = len(
                    [f for f in findings if f.get("status") == "OPEN"]
                )
            except Exception:  # noqa: BLE001, S110
                pass

        # Save master report
        report_file = REPORT_DIR / "assurance_master_report.json"
        report_file.write_text(json.dumps(self.results, indent=2), encoding="utf-8")

        # Print summary
        print("\n" + "=" * 80)
        print("  COMPASS CONTINUOUS PRODUCTION ASSURANCE — SUMMARY")
        print("=" * 80)
        for name, stage in self.results["stages"].items():
            tag = stage.get("status", "?")
            dur = stage.get("duration_s", 0)
            desc = stage.get("description", name)[:55]
            print(f"  {desc:55} | [{tag:7}] ({dur}s)")
        print("-" * 80)
        s = self.results["summary"]
        print(
            f"  Collected: {s['total_stages']} | Passed: {s['passed']} | Failed: {s['failed']} | Blocked: {s['blocked']}"
        )
        print(
            f"  Duration: {s['total_duration_s']}s | Overall: [{s['overall_status']}]"
        )
        if "total_findings" in s:
            print(
                f"  Findings: {s['total_findings']} total | {s.get('open_findings', 0)} open"
            )
        print(f"  Report: {report_file}")
        print("=" * 80)

        return self.results


def main():
    parser = argparse.ArgumentParser(
        description="COMPASS Continuous Production Assurance Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  --full          Full assurance pipeline (default)
  --quick         Inventory + Static + Secret + Regression
  --security      Static + Dependency + Secret + API Security
  --runtime       API + Adversarial + Real Windows + Real Product
  --real-product  Assembled product E2E suite (Backend + Frontend + Real Windows)
  --regression    Pytest regression only
  --performance   Benchmark + Stability only
        """,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--full", action="store_const", const="full", dest="mode")
    group.add_argument("--quick", action="store_const", const="quick", dest="mode")
    group.add_argument(
        "--security", action="store_const", const="security", dest="mode"
    )
    group.add_argument("--runtime", action="store_const", const="runtime", dest="mode")
    group.add_argument(
        "--real-product", action="store_const", const="real_product", dest="mode"
    )
    group.add_argument(
        "--regression", action="store_const", const="regression", dest="mode"
    )
    group.add_argument(
        "--performance", action="store_const", const="performance", dest="mode"
    )
    parser.set_defaults(mode="full")

    args = parser.parse_args()

    runner = AssuranceRunner(mode=args.mode)
    result = runner.run()
    sys.exit(0 if result["summary"]["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
