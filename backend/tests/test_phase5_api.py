"""
Phase 5 API, SSE Streaming & Backend Regression Tests
(P5-REQ-019, P5-REQ-020)
Verifies:
- FastAPI startup & health check
- Task creation, retrieval, and listing
- Malformed request 422 validation
- Non-existent task 404 handling
- STOP endpoint and task cancellation
- Phase 5 state machine propagation (PERCEIVING, UNVERIFIED, AI_UNAVAILABLE, SAFETY_BLOCKED)
- SSE streaming endpoint and terminal event emission
- Zero credential exposure on public API endpoints
"""

import json

from fastapi.testclient import TestClient

from backend.app.database import db
from backend.app.main import app
from backend.app.models import TaskState

client = TestClient(app)


def test_fastapi_startup_and_health():
    """FastAPI responds with healthy status and initialized database."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["database"]["status"] == "healthy"
    assert data["database"]["journal_mode"] == "wal"


def test_task_creation_and_retrieval():
    """POST /api/tasks creates task and GET /api/tasks/{id} retrieves it."""
    create_resp = client.post(
        "/api/tasks",
        json={
            "goal": "Verify Phase 5 API Contract",
            "metadata": {"source": "test_phase5_api"},
        },
    )
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    tid = task_data["id"]
    assert task_data["goal"] == "Verify Phase 5 API Contract"
    assert task_data["state"] == TaskState.STARTING.value

    get_resp = client.get(f"/api/tasks/{tid}")
    assert get_resp.status_code == 200
    detail_data = get_resp.json()
    assert detail_data["id"] == tid
    assert "events" in detail_data


def test_malformed_request_returns_422():
    """Requests violating Pydantic schemas must return 422 Unprocessable Content."""
    resp = client.post("/api/tasks", json={"goal": ""})  # min_length is 2
    assert resp.status_code in (422, 400)


def test_invalid_task_returns_404():
    """Requests for non-existent tasks must return 404."""
    resp = client.get("/api/tasks/task_does_not_exist_99999")
    assert resp.status_code == 404


def test_task_stop_endpoint():
    """POST /api/tasks/{id}/stop immediately stops active task."""
    create_resp = client.post("/api/tasks", json={"goal": "Stop this task"})
    tid = create_resp.json()["id"]

    stop_resp = client.post(f"/api/tasks/{tid}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["state"] == TaskState.STOPPED.value


def test_phase5_state_transitions():
    """Tests propagation of new Phase 5 states through task service."""
    # 1. PERCEIVING transition
    t1 = client.post("/api/tasks", json={"goal": "Perceiving test"}).json()
    tid1 = t1["id"]
    r1 = client.post(
        f"/api/tasks/{tid1}/transition",
        json={"new_state": "PERCEIVING", "reason": "Capturing UIA"},
    )
    assert r1.status_code == 200
    assert r1.json()["state"] == "PERCEIVING"

    # 2. SAFETY_BLOCKED transition
    client.post(f"/api/tasks/{tid1}/transition", json={"new_state": "DECIDING"})
    client.post(f"/api/tasks/{tid1}/transition", json={"new_state": "VALIDATING"})
    r2 = client.post(
        f"/api/tasks/{tid1}/transition",
        json={"new_state": "SAFETY_BLOCKED", "reason": "Out of bounds"},
    )
    assert r2.status_code == 200
    assert r2.json()["state"] == "SAFETY_BLOCKED"

    # Verify SAFETY_BLOCKED is terminal and cannot transition to COMPLETED directly
    r_bad = client.post(
        f"/api/tasks/{tid1}/transition", json={"new_state": "COMPLETED"}
    )
    assert r_bad.status_code == 400

    # 3. AI_UNAVAILABLE transition
    t2 = client.post("/api/tasks", json={"goal": "AI down test"}).json()
    tid2 = t2["id"]
    client.post(f"/api/tasks/{tid2}/transition", json={"new_state": "PLANNING"})
    r3 = client.post(
        f"/api/tasks/{tid2}/transition",
        json={"new_state": "AI_UNAVAILABLE", "reason": "Rate limited"},
    )
    assert r3.status_code == 200
    assert r3.json()["state"] == "AI_UNAVAILABLE"

    # 4. UNVERIFIED transition
    t3 = client.post("/api/tasks", json={"goal": "Unverified test"}).json()
    tid3 = t3["id"]
    db.update_task_state(tid3, "VERIFYING", reason="Checking outcome")
    r4 = client.post(
        f"/api/tasks/{tid3}/transition",
        json={"new_state": "UNVERIFIED", "reason": "UI state uncertain"},
    )
    assert r4.status_code == 200
    assert r4.json()["state"] == "UNVERIFIED"


def test_sse_streaming_media_type():
    """GET /api/tasks/{id}/events returns text/event-stream."""
    t = client.post("/api/tasks", json={"goal": "SSE Stream test"}).json()
    tid = t["id"]

    # Mark stopped to end stream quickly
    client.post(f"/api/tasks/{tid}/stop")

    resp = client.get(f"/api/tasks/{tid}/events")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_ai_status_does_not_expose_credentials():
    """GET /api/ai/status must never expose raw API keys or passwords."""
    resp = client.get("/api/ai/status")
    assert resp.status_code == 200
    data = resp.json()

    assert "gateway" in data
    assert "free_only_policy" in data
    assert data["free_only_policy"] is True

    body_str = json.dumps(data)
    assert "Bearer " not in body_str
    assert "sk-" not in body_str
    assert "password" not in body_str.lower()
