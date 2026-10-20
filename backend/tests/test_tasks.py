"""
Tests for COMPASS /api/tasks lifecycle, transitions, and cancellation.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_task_full_lifecycle():
    # 1. Create task
    create_resp = client.post(
        "/api/tasks", json={"goal": "Open Calculator and compute 42 * 2"}
    )
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    task_id = task_data["id"]
    assert task_data["state"] == "STARTING"
    assert task_data["goal"] == "Open Calculator and compute 42 * 2"

    # 2. Get task detail
    get_resp = client.get(f"/api/tasks/{task_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == task_id
    assert len(detail["events"]) >= 1

    # 3. Transition: STARTING -> UNDERSTANDING
    t1 = client.post(
        f"/api/tasks/{task_id}/transition",
        json={"new_state": "UNDERSTANDING", "reason": "parsing UI"},
    )
    assert t1.status_code == 200
    assert t1.json()["state"] == "UNDERSTANDING"

    # 4. Transition: UNDERSTANDING -> GUIDING
    t2 = client.post(
        f"/api/tasks/{task_id}/transition",
        json={"new_state": "GUIDING", "reason": "displaying next action"},
    )
    assert t2.status_code == 200
    assert t2.json()["state"] == "GUIDING"

    # 5. Stop task
    stop_resp = client.post(f"/api/tasks/{task_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["state"] == "STOPPED"

    # 6. Verify event log has all steps
    final_resp = client.get(f"/api/tasks/{task_id}")
    events = final_resp.json()["events"]
    assert len(events) == 5
    event_types = [e["event_type"] for e in events]
    assert "TASK_CREATED" in event_types
    assert "STATE_TRANSITION" in event_types
    assert "task_stopped" in event_types


def test_delete_task_endpoint():
    create_resp = client.post("/api/tasks", json={"goal": "Task to be deleted"})
    assert create_resp.status_code == 201
    tid = create_resp.json()["id"]

    del_resp = client.delete(f"/api/tasks/{tid}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    get_resp = client.get(f"/api/tasks/{tid}")
    assert get_resp.status_code == 404


def test_clear_completed_tasks_endpoint():
    # Create two tasks: one stopped/terminal, one active
    t1 = client.post("/api/tasks", json={"goal": "Terminal task to clear"}).json()
    client.post(f"/api/tasks/{t1['id']}/stop")

    clear_resp = client.delete("/api/tasks")
    assert clear_resp.status_code == 200
    assert "deleted_count" in clear_resp.json()
    assert clear_resp.json()["deleted_count"] >= 1


def test_get_chat_task_synthetic_detail():
    resp = client.get("/api/tasks/chat-1792260791651")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "chat-1792260791651"
    assert data["state"] == "COMPLETED"
    assert data["metadata"]["guidance_mode"] == "chat"
    assert data["events"] == []

