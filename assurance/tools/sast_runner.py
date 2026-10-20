"""
COMPASS Continuous Production Assurance — Static Analysis (SAST) Runner
Runs Bandit (Python security linter) and custom pattern-based analysis.
Feeds findings into the central FindingRegistry.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

PYTHON_EXE = (
    str(ROOT_DIR / ".venv" / "Scripts" / "python.exe")
    if (ROOT_DIR / ".venv" / "Scripts" / "python.exe").exists()
    else sys.executable
)
REPORT_DIR = ROOT_DIR / "assurance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def check_bandit_installed() -> bool:
    try:
        r = subprocess.run(  # noqa: PLW1510
            [PYTHON_EXE, "-m", "bandit", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def install_bandit() -> bool:
    print("[SAST] Installing bandit...")
    try:
        r = subprocess.run(  # noqa: PLW1510
            [PYTHON_EXE, "-m", "pip", "install", "bandit", "-q"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def run_bandit() -> dict:
    """Run Bandit against all Python source (excluding venv, tests, __pycache__)."""
    targets = [
        "backend",
        "planner",
        "perception",
        "automation",
        "providers",
        "overlay",
    ]
    existing = [str(ROOT_DIR / t) for t in targets if (ROOT_DIR / t).exists()]

    if not existing:
        return {"status": "BLOCKED", "reason": "No scan targets found", "findings": []}

    cmd = [
        PYTHON_EXE,
        "-m",
        "bandit",
        "-r",
        *existing,
        "-f",
        "json",
        "-q",
        "--exclude",
        ".venv,__pycache__,node_modules,.git",
        "-ll",  # Only medium+ severity
    ]

    print(f"[SAST] Running Bandit on: {', '.join(targets)}")
    try:
        proc = subprocess.run(  # noqa: PLW1510
            cmd, capture_output=True, text=True, timeout=120, cwd=str(ROOT_DIR)
        )
        # Bandit returns 1 if findings exist, 0 if clean
        raw_stdout = proc.stdout or ""
        json_start = raw_stdout.find("{")
        json_end = raw_stdout.rfind("}")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            try:
                result = json.loads(raw_stdout[json_start : json_end + 1])
                findings = result.get("results", [])
                metrics = result.get("metrics", {})
                return {
                    "status": "EXECUTED",
                    "returncode": proc.returncode,
                    "findings": findings,
                    "metrics": metrics,
                    "total_findings": len(findings),
                }
            except json.JSONDecodeError as je:
                return {
                    "status": "ERROR",
                    "reason": f"Failed to parse Bandit JSON output: {je}",
                    "raw": raw_stdout[:2000],
                    "findings": [],
                }
        else:
            return {
                "status": "CLEAN" if proc.returncode == 0 else "ERROR",
                "reason": proc.stderr[:500] if proc.stderr else "No output",
                "findings": [],
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "reason": "Bandit timed out after 120s",
            "findings": [],
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "ERROR", "reason": str(e), "findings": []}


def run_sast() -> dict:
    """Full SAST pipeline: install tools if needed, run, return results."""
    results = {"timestamp": time.time(), "tools": {}}

    # 1. Bandit
    if not check_bandit_installed():
        installed = install_bandit()
        if not installed:
            results["tools"]["bandit"] = {
                "status": "BLOCKED — INSTALLATION FAILED",
                "findings": [],
            }
            return results

    bandit_result = run_bandit()
    results["tools"]["bandit"] = bandit_result

    # Save report
    out = REPORT_DIR / "sast_report.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[SAST] Report saved: {out}")
    print(
        f"[SAST] Bandit Status: {bandit_result['status']}, Findings: {bandit_result.get('total_findings', 0)}"
    )

    return results


if __name__ == "__main__":
    run_sast()
