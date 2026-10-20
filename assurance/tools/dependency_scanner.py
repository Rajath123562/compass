"""
COMPASS Continuous Production Assurance — Dependency Security Scanner
Audits Python (pip) and Node (npm) dependencies for known vulnerabilities.
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


def run_pip_audit() -> dict:
    """Run pip-audit for Python dependency vulnerability scanning."""
    # Check/install pip-audit
    try:
        r = subprocess.run(  # noqa: PLW1510
            [PYTHON_EXE, "-m", "pip_audit", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            raise FileNotFoundError
    except Exception:  # noqa: BLE001
        print("[DepSec] Installing pip-audit...")
        subprocess.run(  # noqa: PLW1510
            [PYTHON_EXE, "-m", "pip", "install", "pip-audit", "-q"],
            capture_output=True,
            text=True,
            timeout=60,
        )

    print("[DepSec] Running pip-audit...")
    try:
        proc = subprocess.run(  # noqa: PLW1510
            [PYTHON_EXE, "-m", "pip_audit", "--format=json", "--desc=on"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT_DIR),
        )
        if proc.stdout:
            try:
                data = json.loads(proc.stdout)
                vulns = [d for d in data.get("dependencies", []) if d.get("vulns")]
                return {
                    "status": "EXECUTED",
                    "total_packages": len(data.get("dependencies", [])),
                    "vulnerable_packages": len(vulns),
                    "vulnerabilities": vulns,
                }
            except json.JSONDecodeError:
                return {
                    "status": "EXECUTED",
                    "vulnerable_packages": 0,
                    "vulnerabilities": [],
                    "note": "Clean (no JSON output means no vulns)"
                    if proc.returncode == 0
                    else proc.stderr[:500],
                }
        return {
            "status": "CLEAN" if proc.returncode == 0 else "ERROR",
            "vulnerable_packages": 0,
            "vulnerabilities": [],
            "stderr": proc.stderr[:500] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "vulnerable_packages": 0, "vulnerabilities": []}
    except Exception as e:  # noqa: BLE001
        return {
            "status": "ERROR",
            "vulnerable_packages": 0,
            "vulnerabilities": [],
            "error": str(e),
        }


def run_npm_audit() -> dict:
    """Run npm audit for Node dependency vulnerability scanning."""
    frontend_dir = ROOT_DIR / "frontend"
    if not (frontend_dir / "package.json").exists():
        return {"status": "NOT APPLICABLE", "reason": "No frontend/package.json"}

    print("[DepSec] Running npm audit...")
    try:
        proc = subprocess.run(  # noqa: PLW1510
            ["npm.cmd", "audit", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(frontend_dir),
        )
        if proc.stdout:
            try:
                data = json.loads(proc.stdout)
                total_vulns = data.get("metadata", {}).get("vulnerabilities", {})
                return {
                    "status": "EXECUTED",
                    "vulnerabilities_summary": total_vulns,
                    "advisories_count": len(
                        data.get("advisories", data.get("vulnerabilities", {}))
                    ),
                }
            except json.JSONDecodeError:
                return {"status": "EXECUTED", "raw": proc.stdout[:1000]}
        return {
            "status": "CLEAN" if proc.returncode == 0 else "WARN",
            "stderr": proc.stderr[:500] if proc.stderr else "",
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "BLOCKED", "error": str(e)}


def run_dependency_scan() -> dict:
    """Full dependency security scan."""
    results = {"timestamp": time.time(), "tools": {}}

    results["tools"]["pip_audit"] = run_pip_audit()
    results["tools"]["npm_audit"] = run_npm_audit()

    out = REPORT_DIR / "dependency_report.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[DepSec] Report saved: {out}")
    return results


if __name__ == "__main__":
    run_dependency_scan()
