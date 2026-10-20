"""
COMPASS Master Phase 1 Test and Certification Runner
Executes full suite of unit, integration, persistence, lifecycle, failure-recovery, and clean-launch tests on Windows 11.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_tree(proc):
    if not proc:
        return
    try:
        p = psutil.Process(proc.pid)
        for child in p.children(recursive=True):
            try:
                child.kill()
            except Exception:  # noqa: BLE001, S110
                pass
        p.kill()
    except Exception:  # noqa: BLE001, S110
        pass


def run_step(step_name: str):
    print("\n" + "=" * 60)
    print(f"STEP: {step_name}")
    print("=" * 60)


def main():
    results = {}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)

    # STEP 1: Environment Validation
    run_step("1. Environment Validation")
    cmd_env = [str(VENV_PYTHON), "scripts/validate_env.py"]
    res_env = subprocess.run(cmd_env, cwd=str(ROOT_DIR), capture_output=True, text=True)  # noqa: PLW1510
    print(res_env.stdout)
    results["Environment Validation"] = res_env.returncode == 0

    # STEP 2: Pytest Backend & Overlay Test Suite
    run_step("2. Pytest Unit, Integration, and Failure Test Suite")
    cmd_pytest = [str(VENV_PYTHON), "-m", "pytest", "-v"]
    res_pytest = subprocess.run(  # noqa: PLW1510
        cmd_pytest, cwd=str(ROOT_DIR), capture_output=True, text=True
    )
    print(res_pytest.stdout)
    results["Pytest Suite"] = res_pytest.returncode == 0

    # STEP 3: SQLite Persistence Across Restart
    run_step("3. Database Persistence Across Restart Verification")
    from backend.app.database import DatabaseManager

    test_db_path = ROOT_DIR / "storage" / "persistence_check.db"
    if test_db_path.exists():
        test_db_path.unlink()

    db1 = DatabaseManager(db_path=test_db_path)
    db1.init_db()
    task = db1.create_task(  # noqa: F841
        "task_persist_001", "Verify persistence across restart", "STARTING"
    )
    db1.update_task_state("task_persist_001", "UNDERSTANDING", reason="analyzing UI")
    del db1  # Close instance completely

    # Re-open with new manager instance
    db2 = DatabaseManager(db_path=test_db_path)
    reloaded_task = db2.get_task("task_persist_001")
    reloaded_events = db2.get_task_events("task_persist_001")
    del db2
    if test_db_path.exists():
        test_db_path.unlink()

    persistence_ok = (
        reloaded_task is not None
        and reloaded_task["state"] == "UNDERSTANDING"
        and len(reloaded_events) == 2
    )
    print(
        f"Database Persistence Across Restart: {'PASS' if persistence_ok else 'FAIL'}"
    )
    results["Database Persistence Across Restart"] = persistence_ok

    # STEP 4: Live Backend & Task Flow
    run_step("4. Backend Launch & API Task Flow")
    backend_cmd = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for backend
    backend_ready = False
    for _ in range(25):
        try:
            r = requests.get("http://127.0.0.1:8000/api/health", timeout=0.5)
            if r.status_code == 200:
                backend_ready = True
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.2)

    api_flow_ok = False
    created_task_id = None
    if backend_ready:
        print("[PASS] Backend launched and health check returned 200 OK.")
        # Create Task
        r_create = requests.post(
            "http://127.0.0.1:8000/api/tasks",
            json={"goal": "Create a folder called SIH Demo"},
            timeout=2.0,
        )
        if r_create.status_code == 201:
            created_task_id = r_create.json().get("id")
            print(f"[PASS] Task created with ID: {created_task_id}")
            # Transition
            r_trans = requests.post(
                f"http://127.0.0.1:8000/api/tasks/{created_task_id}/transition",
                json={"new_state": "UNDERSTANDING", "reason": "parsing UI"},
                timeout=2.0,
            )
            # Stop
            r_stop = requests.post(
                f"http://127.0.0.1:8000/api/tasks/{created_task_id}/stop", timeout=2.0
            )
            if r_trans.status_code == 200 and r_stop.status_code == 200:
                api_flow_ok = True
                print("[PASS] Task transitions and stop mechanism verified live.")
    results["Backend & Live API Flow"] = api_flow_ok

    # STEP 5: Frontend Vite Dev Server Launch & Probe
    run_step("5. Frontend Launch & HTTP Probe")
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=str(ROOT_DIR / "frontend"),
        shell=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frontend_ready = False
    for _ in range(30):
        try:
            r = requests.get("http://127.0.0.1:5173", timeout=0.5)
            if r.status_code == 200 and "COMPASS" in r.text:
                frontend_ready = True
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    print(
        f"Frontend HTTP Probe: {'PASS (HTML served with COMPASS title)' if frontend_ready else 'FAIL'}"
    )
    results["Frontend Launch & Probe"] = frontend_ready

    # STEP 6: Backend Disconnect & Recovery
    run_step("6. Backend Disconnect & Recovery Test")
    # Kill backend
    kill_tree(backend_proc)
    time.sleep(1)
    port_8000_closed = not is_port_open(8000)
    print(f"[PASS] Backend stopped. Port 8000 closed: {port_8000_closed}")

    # Verify connection failure
    disconnect_detected = False
    try:
        requests.get("http://127.0.0.1:8000/api/health", timeout=0.5)
    except Exception:  # noqa: BLE001
        disconnect_detected = True
    print(f"[PASS] Frontend/Client detects connection loss: {disconnect_detected}")

    # Restart backend
    backend_proc_2 = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    recovery_ok = False
    for _ in range(25):
        try:
            r = requests.get("http://127.0.0.1:8000/api/health", timeout=0.5)
            if r.status_code == 200:
                recovery_ok = True
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    print(f"[PASS] Backend restarted and recovered: {recovery_ok}")
    results["Backend Disconnect & Recovery"] = (
        port_8000_closed and disconnect_detected and recovery_ok
    )

    # STEP 7: PySide6 Overlay Standalone Launch Test
    run_step("7. PySide6 Overlay Standalone Launch & Clean Close")
    overlay_cmd = [str(VENV_PYTHON), "-m", "overlay.launcher", "--duration", "1.0"]
    ov_res = subprocess.run(  # noqa: PLW1510
        overlay_cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=10
    )
    overlay_ok = ov_res.returncode == 0 and "Closed cleanly" in ov_res.stdout
    print(f"Overlay Launch & Close: {'PASS' if overlay_ok else 'FAIL'}")
    results["Overlay Foundation"] = overlay_ok

    # STEP 8: Clean Shutdown and No Orphan Processes
    run_step("8. Clean Shutdown & Orphan Process Check")
    # Clean up test processes
    kill_tree(backend_proc_2)
    kill_tree(frontend_proc)
    time.sleep(1)

    stop_cmd = [str(VENV_PYTHON), "scripts/stop_compass.py"]
    stop_res = subprocess.run(  # noqa: PLW1510
        stop_cmd, cwd=str(ROOT_DIR), capture_output=True, text=True
    )
    print(stop_res.stdout)
    clean_shutdown_ok = (
        stop_res.returncode == 0 and not is_port_open(8000) and not is_port_open(5173)
    )
    results["Clean Shutdown & No Orphans"] = clean_shutdown_ok

    # Summary
    print("\n" + "=" * 60)
    print("PHASE 1 VERIFICATION SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"{status:7} {name}")
    print("=" * 60)
    print(f"OVERALL STATUS: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    passed = main()
    sys.exit(0 if passed else 1)
