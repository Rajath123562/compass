"""
Tests for COMPASS Failure Handling, Invalid Payloads, and Edge Cases.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_malformed_task_creation():
    # Empty goal
    resp = client.post("/api/tasks", json={"goal": ""})
    assert resp.status_code == 422
    assert resp.json()["error"] is True

    # Missing goal field
    resp2 = client.post("/api/tasks", json={})
    assert resp2.status_code == 422
    assert resp2.json()["error"] is True


def test_nonexistent_task_queries():
    resp = client.get("/api/tasks/task_does_not_exist_9999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_invalid_state_transition():
    # Create task (starts at STARTING)
    create_resp = client.post("/api/tasks", json={"goal": "Test invalid transition"})
    task_id = create_resp.json()["id"]

    # Try invalid jump: STARTING -> COMPLETED directly (not permitted by state machine)
    resp = client.post(
        f"/api/tasks/{task_id}/transition",
        json={"new_state": "COMPLETED", "reason": "invalid jump"},
    )
    assert resp.status_code == 400
    assert "Invalid state transition" in resp.json()["detail"]


def test_transition_nonexistent_task():
    resp = client.post(
        "/api/tasks/task_invalid_xyz/transition", json={"new_state": "GUIDING"}
    )
    assert resp.status_code == 404


def test_unknown_route_404():
    resp = client.get("/api/unknown_route_xyz")
    assert resp.status_code == 404
    assert resp.json()["error"] is True
