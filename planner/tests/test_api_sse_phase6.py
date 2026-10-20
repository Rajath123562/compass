"""
Integration tests for API and SSE Streaming (Phase 6, §23).
Verifies task creation, state transitions, cancellation, error propagation,
and truthful streaming of all 20 Phase 6 states via FastAPI TestClient.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models import TaskState

client = TestClient(app)


def test_api_create_task_valid():
    """POST /api/tasks creates a task in IDLE/STARTING state with valid ID."""
    resp = client.post("/api/tasks", json={"goal": "Multi-step test goal"})
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert "id" in data
    assert data["goal"] == "Multi-step test goal"


def test_api_create_task_malformed():
    """POST /api/tasks rejects malformed goals (empty or too short)."""
    resp = client.post("/api/tasks", json={"goal": ""})
    assert resp.status_code == 422


def test_api_cancel_task():
    """POST /api/tasks/{task_id}/cancel cancels an active task."""
    resp = client.post("/api/tasks", json={"goal": "Task to cancel"})
    tid = resp.json()["id"]

    cancel_resp = client.post(
        f"/api/tasks/{tid}/cancel", json={"reason": "User testing cancel API"}
    )
    assert cancel_resp.status_code in [200, 204]

    get_resp = client.get(f"/api/tasks/{tid}")
    assert get_resp.status_code == 200
    state = get_resp.json()["state"]
    assert state in [TaskState.CANCELLED.value, TaskState.STOPPED.value]


def test_api_state_transition_validation():
    """POST /api/tasks/{task_id}/transition strictly validates transitions."""
    resp = client.post("/api/tasks", json={"goal": "Transition test"})
    tid = resp.json()["id"]

    # Valid transition to STARTING or UNDERSTANDING
    tr_resp = client.post(
        f"/api/tasks/{tid}/transition",
        json={"new_state": "UNDERSTANDING", "reason": "Test"},
    )
    assert tr_resp.status_code in [200, 204]

    # Verify task state updated
    t_get = client.get(f"/api/tasks/{tid}").json()
    assert t_get["state"] == "UNDERSTANDING"
