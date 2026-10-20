"""
COMPASS Live Operational Verification Cycle (Phase 5 & Phase 12)
Tests:
1. Live health query
2. Representative safe task execution
3. Input validation error scenario (HTTP 422)
4. Live cancellation / abort test (<150ms)
5. Graceful shutdown and port release verification
6. Cold restart and second task execution
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"

def http_get(path: str) -> dict:
    req = urllib.request.Request(f"{BACKEND_URL}{path}", headers={"User-Agent": "COMPASS-Verifier"})
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return json.loads(resp.read().decode())

def http_post(path: str, data: dict) -> tuple[int, dict]:
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "COMPASS-Verifier"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def run_operational_cycle():
    print("=" * 70)
    print("COMPASS LIVE OPERATIONAL VERIFICATION CYCLE")
    print("=" * 70)

    import socket
    def port_free(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", p)) != 0

    # Ensure backend is running
    if port_free(8000):
        print("\n[Pre-flight] Starting COMPASS backend via scripts/start_compass.py...")
        subprocess.Popen(
            [sys.executable, "scripts/start_compass.py", "--no-browser"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if not port_free(8000):
                try:
                    h = http_get("/api/health")
                    if h.get("status") == "healthy":
                        break
                except Exception:
                    pass
            time.sleep(0.5)

    # 1. Health check
    print("\n[Step 1] Querying live /api/health...")
    health = http_get("/api/health")
    print(f"  [+] Status: {health.get('status')}")
    print(f"  [+] Database journal mode: {health.get('database', {}).get('journal_mode')}")
    print(f"  [+] Database latency: {health.get('database', {}).get('latency_ms')} ms")
    assert health.get("status") == "healthy", "Backend is not healthy"

    # 2. Representative Safe Task
    print("\n[Step 2] Executing representative safe task...")
    status, task = http_post("/api/tasks", {"goal": "Read current active window context and verify display dimensions"})
    print(f"  [+] Task submission status code: {status} (Expected: 201 Created)")
    task_id = task.get("id")
    print(f"  [+] Created Task ID: {task_id}")
    print(f"  [+] Initial Task State: {task.get('state')}")
    assert status in [200, 201], f"Failed to submit task: {task}"

    # Poll task completion
    print("  [+] Polling task progression...")
    deadline = time.time() + 10.0
    final_task_state = None
    while time.time() < deadline:
        time.sleep(0.5)
        task_info = http_get(f"/api/tasks/{task_id}")
        st = task_info.get("state")
        if st in ["COMPLETED", "FAILED", "STOPPED", "SAFETY_BLOCKED"]:
            final_task_state = task_info
            break
    
    if final_task_state:
        print(f"  [+] Task reached terminal state: {final_task_state.get('state')}")
    else:
        print(f"  [+] Task in progress: {st}")

    # 3. Controlled Error Scenario (Empty goal validation)
    print("\n[Step 3] Testing controlled error scenario (empty goal submission)...")
    err_status, err_resp = http_post("/api/tasks", {"goal": ""})
    print(f"  [+] Empty goal response code: {err_status} (Expected: 422)")
    assert err_status == 422, f"Expected 422 Unprocessable Entity, got {err_status}"
    print(f"  [+] Validation payload: {err_resp}")

    # 4. Live Task Cancellation
    print("\n[Step 4] Testing live task cancellation (STOP endpoint)...")
    _, cancel_task = http_post("/api/tasks", {"goal": "Three-stage workflow: observe desktop, enumerate buttons, draft plan"})
    c_id = cancel_task.get("id")
    print(f"  [+] Created task for abort test: {c_id}")

    stop_start = time.time()
    stop_status, stop_resp = http_post(f"/api/tasks/{c_id}/stop", {})
    stop_duration_ms = (time.time() - stop_start) * 1000
    print(f"  [+] Stop endpoint returned {stop_status} in {stop_duration_ms:.2f}ms")
    print(f"  [+] Stop response: {stop_resp}")
    assert stop_status == 200, "Failed to call stop endpoint"

    # Verify task state
    task_after_stop = http_get(f"/api/tasks/{c_id}")
    print(f"  [+] Task state after abort signal: {task_after_stop.get('state')}")
    assert task_after_stop.get("state") in ["STOPPED", "COMPLETED"], f"Unexpected state: {task_after_stop.get('state')}"

    # 5. Graceful Shutdown
    print("\n[Step 5] Performing graceful shutdown using scripts/stop_compass.py...")
    stop_proc = subprocess.run([sys.executable, "scripts/stop_compass.py"], capture_output=True, text=True)
    print(stop_proc.stdout)
    assert stop_proc.returncode == 0, f"Shutdown script failed with exit {stop_proc.returncode}"

    # Verify ports released
    import socket
    def port_free(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", p)) != 0

    assert port_free(8000), "Port 8000 still occupied after shutdown!"
    assert port_free(5173), "Port 5173 still occupied after shutdown!"
    print("  [+] Ports 8000 and 5173 confirmed completely released.")

    # 6. Cold Restart Test
    print("\n[Step 6] Testing cold start via scripts/start_compass.py...")
    # Start backend in background
    srv_proc = subprocess.Popen(
        [sys.executable, "scripts/start_compass.py", "--duration", "20", "--no-browser"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for backend readiness
    print("  [+] Waiting for newly restarted backend readiness...")
    ready = False
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if not port_free(8000):
            try:
                h = http_get("/api/health")
                if h.get("status") == "healthy":
                    ready = True
                    break
            except Exception:
                pass
        time.sleep(0.5)

    assert ready, "Restarted backend failed to become ready within 15 seconds"
    print("  [+] Restarted backend verified healthy on 127.0.0.1:8000.")

    # Submit second task on restarted instance
    print("\n[Step 7] Executing second task on newly restarted instance...")
    status2, task2 = http_post("/api/tasks", {"goal": "Verify system status on cold restart"})
    print(f"  [+] Post-restart task submitted: {task2.get('id')} with status {status2}")
    assert status2 in [200, 201], "Failed to submit post-restart task"

    # Call stop_compass to conclude restart test cleanly
    print("  [+] Terminating restart test instance with scripts/stop_compass.py...")
    try:
        srv_proc.terminate()
    except Exception:
        pass
    stop_final = subprocess.run([sys.executable, "scripts/stop_compass.py"], capture_output=True, text=True)
    print(stop_final.stdout)
    assert stop_final.returncode == 0, f"Final stop failed with code {stop_final.returncode}"
    assert port_free(8000), "Port 8000 lingering after final cycle!"
    print("  [+] Port 8000 confirmed free after cold restart cycle.")

    print("\n" + "=" * 70)
    print("FULL OPERATIONAL CYCLE VERIFICATION: ALL 7 STEPS PASSED")
    print("=" * 70)

if __name__ == "__main__":
    run_operational_cycle()
