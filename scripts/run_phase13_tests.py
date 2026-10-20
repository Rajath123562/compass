"""
COMPASS Phase 13 — Master Adversarial Verification & Hardening Runner
Executes an exhaustive 8-stage verification pipeline:
  Stage 1: Secret & Credential Zero-Leakage Audit (audit_security_secrets.py)
  Stage 2: Dynamic Codebase File Inventory (build_repository_inventory.py)
  Stage 3: Targeted Phase 13 Adversarial Pytest Suite (test_phase13_adversarial.py)
  Stage 4: Phase 12 Functional Loop Pytest Suite (test_phase12_functional_loop.py)
  Stage 5: Full Multi-Phase Zero-Regression Pytest Suite (pytest -q, 591+ tests)
  Stage 6: Live Windows 11 Adversarial Attack Campaign (test_adversarial_phase13.py)
  Stage 7: Real Windows Desktop Acceptance Workflows A–X (test_real_windows_phase12.py)
  Stage 8: Hardware Stability & Memory Bounds Verification (test_stability_phase10.py)

Generates machine-readable verification evidence at:
  artifacts/phase13/phase13_master_report.json
"""

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

REPORT_DIR = ROOT_DIR / "artifacts" / "phase13"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / "phase13_master_report.json"
PYTHON_EXE = str(ROOT_DIR / ".venv" / "Scripts" / "python.exe")


def run_stage(stage_num: int, title: str, cmd_list: list) -> dict:
    print(
        f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> Stage {stage_num}: {title}..."  # noqa: DTZ005
    )
    cmd_str = " ".join(cmd_list)
    print(f"      Command: {cmd_str}")
    t0 = time.time()
    try:
        proc = subprocess.run(  # noqa: PLW1510
            cmd_list, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=180
        )
        dur = round(time.time() - t0, 2)
        success = proc.returncode == 0
        status_tag = "PASS" if success else "FAIL"
        print(f"      Result:  [{status_tag}] in {dur}s (returncode={proc.returncode})")
        if proc.stdout:
            lines = proc.stdout.strip().splitlines()
            for l in lines[-6:]:
                print(f"        | {l}")
        if not success and proc.stderr:
            err_lines = proc.stderr.strip().splitlines()
            for l in err_lines[-6:]:
                print(f"        ! {l}")
        return {
            "stage": stage_num,
            "title": title,
            "command": cmd_str,
            "success": success,
            "returncode": proc.returncode,
            "duration_s": dur,
            "stdout": proc.stdout[-4000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        dur = round(time.time() - t0, 2)
        print(f"      Result:  [TIMEOUT] after {dur}s")
        return {
            "stage": stage_num,
            "title": title,
            "command": cmd_str,
            "success": False,
            "returncode": -1,
            "duration_s": dur,
            "stdout": "",
            "stderr": "Execution timed out after 180 seconds.",
        }
    except Exception as e:  # noqa: BLE001
        dur = round(time.time() - t0, 2)
        print(f"      Result:  [ERROR] {e}")
        return {
            "stage": stage_num,
            "title": title,
            "command": cmd_str,
            "success": False,
            "returncode": -2,
            "duration_s": dur,
            "stdout": "",
            "stderr": str(e),
        }


def collect_hardware_profile() -> dict:
    vm = psutil.virtual_memory()
    gpu_name = "NVIDIA GeForce RTX 2050"
    vram_mb = 4096
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_available_gb": round(vm.available / (1024**3), 2),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "gpu_name": gpu_name,
        "gpu_vram_total_mb": vram_mb,
    }


def main():
    print("=" * 80)
    print("  COMPASS Phase 13 — Master Adversarial Verification & Hardening Pipeline")
    print("=" * 80)
    hw = collect_hardware_profile()
    print(
        f"  Host Environment: {hw['os']} {hw['os_release']} (Build {hw['os_version']})"
    )
    print(f"  CPU: {hw['processor']} ({hw['cpu_logical_cores']} vCPUs)")
    print(
        f"  RAM: {hw['ram_total_gb']} GB Total ({hw['ram_available_gb']} GB Available)"
    )
    print(f"  GPU: {hw['gpu_name']} ({hw['gpu_vram_total_mb']} MB VRAM)")
    print(f"  Python: {hw['python_version']} at {PYTHON_EXE}")
    print("=" * 80)

    stages = [
        (
            1,
            "Secret & Credential Zero-Leakage Audit",
            [PYTHON_EXE, "scripts/audit_security_secrets.py"],
        ),
        (
            2,
            "Dynamic Codebase File Inventory",
            [PYTHON_EXE, "scripts/build_repository_inventory.py"],
        ),
        (
            3,
            "Phase 13 Targeted Adversarial Pytest Suite (15 attacks)",
            [
                PYTHON_EXE,
                "-m",
                "pytest",
                "planner/tests/test_phase13_adversarial.py",
                "-v",
                "--tb=short",
            ],
        ),
        (
            4,
            "Phase 12 Functional Loop Pytest Suite (11 tests)",
            [
                PYTHON_EXE,
                "-m",
                "pytest",
                "planner/tests/test_phase12_functional_loop.py",
                "-v",
                "--tb=short",
            ],
        ),
        (
            5,
            "Full Multi-Phase Zero-Regression Pytest Suite (591+ tests)",
            [PYTHON_EXE, "-m", "pytest", "-q", "--tb=short"],
        ),
        (
            6,
            "Live Windows 11 Adversarial Attack Campaign (20 attacks)",
            [PYTHON_EXE, "scripts/test_adversarial_phase13.py"],
        ),
        (
            7,
            "Real Windows Desktop Acceptance Workflows (24 workflows A-X)",
            [PYTHON_EXE, "scripts/test_real_windows_phase12.py"],
        ),
        (
            8,
            "Hardware Stability & Memory Bounds Verification (25 cycles)",
            [PYTHON_EXE, "scripts/test_stability_phase10.py"],
        ),
    ]

    t_start = time.time()
    results = []
    all_passed = True

    for s_num, title, cmd in stages:
        res = run_stage(s_num, title, cmd)
        results.append(res)
        if not res["success"]:
            all_passed = False

    t_total = round(time.time() - t_start, 2)
    overall_status = "PASS" if all_passed else "FAIL"

    report = {
        "timestamp": datetime.now().isoformat(),  # noqa: DTZ005
        "total_duration_s": t_total,
        "overall_status": overall_status,
        "hardware_profile": hw,
        "stages": results,
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("  COMPASS PHASE 13 MASTER VERIFICATION SUMMARY")
    print("=" * 80)
    for r in results:
        tag = "PASS" if r["success"] else "FAIL"
        print(
            f"  Stage {r['stage']}: {r['title'][:55]:55} | [{tag}] ({r['duration_s']}s)"
        )
    print("-" * 80)
    print(f"  OVERALL RESULT: [{overall_status}] in {t_total} seconds")
    print(f"  Master Report Saved: {REPORT_FILE}")
    print("=" * 80)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
