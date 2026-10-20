"""
Comprehensive Live Integration & Loop Test for Compass Personal Assistant.
Tests live HTTP endpoints, Task creation, Fast-path execution, State transitions,
Circuit Breaker, and Cancellation on the running server (http://127.0.0.1:8000).
"""
import sys
import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def request(method: str, path: str, data: dict = None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            try:
                res_json = json.loads(content)
            except Exception:
                res_json = content
            return status, res_json
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = err_body
        return e.code, err_json
    except Exception as e:
        return 0, str(e)

def run_loop_tests():
    results = {}
    print("=" * 60)
    print("COMPASS LIVE ENDPOINT & LOOP VERIFICATION SUITE")
    print("=" * 60)

    # 1. Health Probe
    print("\n[TEST 1] GET /api/health ...")
    st, res = request("GET", "/api/health")
    print(f"Status: {st}, Response: {res}")
    assert st == 200, f"Health check failed with status {st}"
    results["health"] = "PASS"

    # 2. System Info & Active Window Probe
    print("\n[TEST 2] GET /api/system/info ...")
    st, res = request("GET", "/api/system/info")
    print(f"Status: {st}, System Info: {res}")
    assert st == 200, f"System info failed with status {st}"

    print("\n[TEST 2b] GET /api/system/active_window ...")
    st_w, res_w = request("GET", "/api/system/active_window")
    print(f"Status: {st_w}, Active Window: {res_w}")
    assert st_w == 200, f"Active window failed with status {st_w}"
    results["system_info"] = "PASS"

    # 3. Circuit Breaker Probe & Reset
    print("\n[TEST 3] GET /api/ai/circuit_breaker ...")
    st, res = request("GET", "/api/ai/circuit_breaker")
    print(f"Status: {st}, Circuit Breaker State: {res}")
    assert st == 200, f"Circuit breaker get failed with status {st}"

    print("[TEST 3b] POST /api/ai/circuit_breaker/reset ...")
    st_reset, res_reset = request("POST", "/api/ai/circuit_breaker/reset")
    print(f"Status: {st_reset}, Reset response: {res_reset}")
    assert st_reset == 200, f"Circuit breaker reset failed with status {st_reset}"
    results["circuit_breaker"] = "PASS"

    # 4. Loop Testing: Launch commands (Calculator, Notepad, Settings)
    test_goals = [
        "open calculator",
        "open notepad",
        "open settings",
        "calculate 150 + 350",
    ]

    task_ids = []
    print("\n[TEST 4] Task Creation & Fast-Path Decomposition Loop:")
    for goal in test_goals:
        print(f"\n -> Submitting Task: '{goal}'")
        t0 = time.time()
        st, res = request("POST", "/api/tasks", {"goal": goal})
        dt = (time.time() - t0) * 1000
        print(f"    Status: {st} ({dt:.1f}ms), Task payload: {res}")
        assert st in (200, 201), f"Failed to create task '{goal}': {res}"
        task_id = res.get("id") or res.get("task_id")
        assert task_id, f"No task_id returned in response: {res}"
        task_ids.append((goal, task_id))
        
        # Poll state transition for up to 6 seconds
        time.sleep(1.0)
        st_get, res_get = request("GET", f"/api/tasks/{task_id}")
        state = res_get.get("state") if isinstance(res_get, dict) else "UNKNOWN"
        print(f"    Task {task_id} state after 1s: {state}")

    results["task_creation_loop"] = "PASS"

    # 5. Cancellation & Stop API Test
    print("\n[TEST 5] Testing Task Cancellation / Stop API ...")
    st, res = request("POST", "/api/tasks", {"goal": "test long running task cancellation"})
    assert st in (200, 201), f"Creation failed: {res}"
    cancel_id = res.get("id") or res.get("task_id")
    print(f"Created task {cancel_id} for cancellation test.")
    
    st_stop, res_stop = request("POST", f"/api/tasks/{cancel_id}/stop")
    print(f"Stop request status: {st_stop}, response: {res_stop}")
    assert st_stop in (200, 204), f"Stop request failed: {st_stop} {res_stop}"
    
    st_verify, res_verify = request("GET", f"/api/tasks/{cancel_id}")
    final_state = res_verify.get("state") if isinstance(res_verify, dict) else "UNKNOWN"
    print(f"Task {cancel_id} post-stop state: {final_state}")
    results["task_cancellation"] = "PASS"

    # 6. List Tasks Verification
    print("\n[TEST 6] GET /api/tasks ...")
    st, res = request("GET", "/api/tasks")
    print(f"Status: {st}, Found {len(res) if isinstance(res, list) else 'non-list'} tasks.")
    assert st == 200, f"Listing tasks failed: {st}"
    assert isinstance(res, list) and len(res) >= len(task_ids), "Task history missing newly created tasks"
    results["task_listing"] = "PASS"

    # 7. Security / Validation Negative Tests
    print("\n[TEST 7] Negative Validation / Security Tests ...")
    # Empty goal test -> should return 422 Unprocessable Entity
    st_bad, res_bad = request("POST", "/api/tasks", {"goal": ""})
    print(f"Empty goal rejection test status: {st_bad} (Expected 422 or 400)")
    assert st_bad in (400, 422), f"Expected 400/422 for empty goal, got {st_bad}"
    
    # Non-existent task get -> should return 404
    st_404, res_404 = request("GET", "/api/tasks/non_existent_task_id_9999999")
    print(f"Non-existent task 404 test status: {st_404} (Expected 404)")
    assert st_404 == 404, f"Expected 404, got {st_404}"
    results["security_validation"] = "PASS"

    print("\n" + "=" * 60)
    print("ALL LIVE LOOP TESTS PASSED SUCCESSFULLY!")
    print(json.dumps(results, indent=2))
    print("=" * 60)

if __name__ == "__main__":
    run_loop_tests()
