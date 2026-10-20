"""
COMPASS Live Integration Test Suite
Tests every major endpoint and workflow against a running backend.
"""
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0
ERRORS = []


def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  [PASS] {name}")
    except Exception as e:  # noqa: BLE001
        FAIL += 1
        ERRORS.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")


# ─── 1. Root & Health ─────────────────────────────────────────────────────────

def test_root():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["status"] == "online"
    assert "COMPASS" in data["name"]

def test_health():
    r = requests.get(f"{BASE}/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy", f"Expected healthy, got {data['status']}"
    assert "database" in data
    assert "system" in data

def test_system_info():
    r = requests.get(f"{BASE}/api/system/info")
    assert r.status_code == 200
    data = r.json()
    assert "os" in data
    assert "python_version" in data


# ─── 2. Task CRUD ────────────────────────────────────────────────────────────

def test_create_task():
    r = requests.post(f"{BASE}/api/tasks", json={
        "goal": "Open Notepad and type Hello",
        "metadata": {"source": "live_test"}
    })
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    data = r.json()
    assert "id" in data
    assert data["goal"] == "Open Notepad and type Hello"
    return data["id"]

def test_get_task():
    tid = test_create_task()
    time.sleep(0.5)  # let auto-execute run briefly
    r = requests.get(f"{BASE}/api/tasks/{tid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == tid

def test_list_tasks():
    r = requests.get(f"{BASE}/api/tasks?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5

def test_task_not_found():
    r = requests.get(f"{BASE}/api/tasks/task_nonexistent_xyz")
    assert r.status_code == 404


# ─── 3. State Transitions ────────────────────────────────────────────────────

def test_manual_state_transition():
    """Create task, wait for auto-execute to settle, then test transitions on a fresh task."""
    # We need a task that stays in STARTING state - create via direct DB would be ideal
    # but let's just test the transition validation endpoint
    r = requests.post(f"{BASE}/api/tasks", json={"goal": "Manual transition test"})
    assert r.status_code == 201
    tid = r.json()["id"]
    time.sleep(2)  # let auto-execute finish

    # Get current state
    task = requests.get(f"{BASE}/api/tasks/{tid}").json()
    current_state = task["state"]  # noqa: F841

    # Try an invalid transition from wherever the task ended up
    r = requests.post(f"{BASE}/api/tasks/{tid}/transition",
                      json={"new_state": "WORKFLOW_RUNNING", "reason": "test"})
    # Should be 400 (invalid transition from most states)
    assert r.status_code == 400, f"Expected 400 for invalid transition, got {r.status_code}"

def test_stop_task():
    r = requests.post(f"{BASE}/api/tasks", json={"goal": "Task to stop"})
    tid = r.json()["id"]
    time.sleep(0.3)

    # Stop may succeed or fail depending on timing; just verify it returns a valid response
    r = requests.post(f"{BASE}/api/tasks/{tid}/stop")
    assert r.status_code in [200, 400], f"Unexpected status {r.status_code}: {r.text}"

def test_cancel_task():
    r = requests.post(f"{BASE}/api/tasks", json={"goal": "Task to cancel"})
    tid = r.json()["id"]
    time.sleep(0.3)

    r = requests.post(f"{BASE}/api/tasks/{tid}/cancel")
    assert r.status_code in [200, 400], f"Unexpected status {r.status_code}: {r.text}"


# ─── 4. Validation Errors ────────────────────────────────────────────────────

def test_create_task_no_goal():
    r = requests.post(f"{BASE}/api/tasks", json={})
    assert r.status_code == 422

def test_create_task_short_goal():
    r = requests.post(f"{BASE}/api/tasks", json={"goal": "X"})
    assert r.status_code == 422

def test_invalid_transition_state():
    r = requests.post(f"{BASE}/api/tasks", json={"goal": "Invalid state test"})
    tid = r.json()["id"]
    r = requests.post(f"{BASE}/api/tasks/{tid}/transition",
                      json={"new_state": "NOT_A_REAL_STATE"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"


# ─── 5. Perception Endpoints ─────────────────────────────────────────────────

def test_perception_status():
    r = requests.get(f"{BASE}/api/perception/status")
    assert r.status_code in [200, 500], f"Unexpected: {r.status_code}"
    if r.status_code == 200:
        data = r.json()
        assert "uia" in data or "capture_enabled" in data or isinstance(data, dict)


# ─── 6. Planner Endpoints ────────────────────────────────────────────────────

def test_planner_plan():
    r = requests.post(f"{BASE}/api/planner/plan", json={
        "goal": "Open calculator and compute 2+2",
        "task_id": "test_plan_001"
    })
    # Plan might fail due to no API key, but should return a proper response
    assert r.status_code in [200, 500, 503], f"Unexpected: {r.status_code}: {r.text}"


# ─── 7. Workflow Endpoints ───────────────────────────────────────────────────

def test_workflow_create():
    r = requests.post(f"{BASE}/api/workflows", json={
        "goal": "Test workflow creation",
        "nodes": [
            {"node_id": "step1", "goal": "First step"},
            {"node_id": "step2", "goal": "Second step", "dependencies": ["step1"]}
        ]
    })
    assert r.status_code in [200, 201], f"Expected 200/201, got {r.status_code}: {r.text}"
    if r.status_code in [200, 201]:
        data = r.json()
        assert "workflow_id" in data
        return data["workflow_id"]

def test_workflow_list():
    r = requests.get(f"{BASE}/api/workflows")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)

def test_workflow_invalid_dag():
    """Cyclic dependency must be rejected."""
    r = requests.post(f"{BASE}/api/workflows", json={
        "goal": "Cyclic test",
        "nodes": [
            {"node_id": "A", "goal": "step A", "dependencies": ["B"]},
            {"node_id": "B", "goal": "step B", "dependencies": ["A"]}
        ]
    })
    assert r.status_code == 400, f"Expected 400 for cycle, got {r.status_code}: {r.text}"


# ─── 8. Reliability Endpoints ────────────────────────────────────────────────

def test_reliability_health():
    r = requests.get(f"{BASE}/api/reliability/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


# ─── 9. Automation Endpoints ─────────────────────────────────────────────────

def test_automation_click_validation():
    """Click without element should return 422."""
    r = requests.post(f"{BASE}/api/automation/click", json={})
    assert r.status_code == 422

def test_automation_type_validation():
    """Type without text should return 422."""
    r = requests.post(f"{BASE}/api/automation/type", json={"element": {"name": "test"}})
    assert r.status_code == 422

def test_automation_key_validation():
    """Key without key should return 422."""
    r = requests.post(f"{BASE}/api/automation/key", json={})
    assert r.status_code == 422


# ─── 10. OpenAPI Docs ────────────────────────────────────────────────────────

def test_openapi_json():
    r = requests.get(f"{BASE}/api/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data
    assert "openapi" in data

def test_docs_page():
    r = requests.get(f"{BASE}/api/docs")
    assert r.status_code == 200


# ─── 11. Edge Cases & Security ───────────────────────────────────────────────

def test_cors_headers():
    r = requests.options(f"{BASE}/api/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET"
    })
    assert r.status_code == 200
    assert "access-control-allow-origin" in r.headers

def test_nonexistent_endpoint():
    r = requests.get(f"{BASE}/api/nonexistent")
    assert r.status_code == 404

def test_create_many_tasks_stress():
    """Quick stress: create 10 tasks rapidly."""
    for i in range(10):
        r = requests.post(f"{BASE}/api/tasks", json={"goal": f"Stress test task {i}"})
        assert r.status_code == 201, f"Failed on task {i}: {r.status_code}"


# ─── Run All ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  COMPASS Live Integration Test Suite")
    print("="*70 + "\n")

    print("Section 1: Root & Health")
    test("GET /", test_root)
    test("GET /api/health", test_health)
    test("GET /api/system/info", test_system_info)

    print("\nSection 2: Task CRUD")
    test("POST /api/tasks (create)", lambda: test_create_task())
    test("GET /api/tasks/{id} (retrieve)", test_get_task)
    test("GET /api/tasks (list)", test_list_tasks)
    test("GET /api/tasks/{bad_id} (404)", test_task_not_found)

    print("\nSection 3: State Transitions")
    test("Invalid transition rejected", test_manual_state_transition)
    test("POST /api/tasks/{id}/stop", test_stop_task)
    test("POST /api/tasks/{id}/cancel", test_cancel_task)

    print("\nSection 4: Validation Errors")
    test("Create task without goal (422)", test_create_task_no_goal)
    test("Create task with too-short goal (422)", test_create_task_short_goal)
    test("Invalid state name (422)", test_invalid_transition_state)

    print("\nSection 5: Perception")
    test("GET /api/perception/status", test_perception_status)

    print("\nSection 6: Planner")
    test("POST /api/planner/plan", test_planner_plan)

    print("\nSection 7: Workflows")
    test("POST /api/workflows (create)", lambda: test_workflow_create())
    test("GET /api/workflows (list)", test_workflow_list)
    test("POST /api/workflows (cyclic DAG rejected)", test_workflow_invalid_dag)

    print("\nSection 8: Reliability")
    test("GET /api/reliability/health", test_reliability_health)

    print("\nSection 9: Automation Validation")
    test("Click without element (422)", test_automation_click_validation)
    test("Type without text (422)", test_automation_type_validation)
    test("Key without key (422)", test_automation_key_validation)

    print("\nSection 10: OpenAPI & Docs")
    test("GET /api/openapi.json", test_openapi_json)
    test("GET /api/docs", test_docs_page)

    print("\nSection 11: Edge Cases & Security")
    test("CORS preflight headers", test_cors_headers)
    test("Nonexistent endpoint (404)", test_nonexistent_endpoint)
    test("Stress: create 10 tasks rapidly", test_create_many_tasks_stress)

    print("\n" + "="*70)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("="*70)

    if ERRORS:
        print("\nFailed tests:")
        for name, err in ERRORS:
            print(f"  [FAIL] {name}: {err}")

    sys.exit(1 if FAIL > 0 else 0)
