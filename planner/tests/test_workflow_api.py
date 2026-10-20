"""
Tests for Phase 8 Workflows REST API & SSE Endpoints (Gate 32).
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_api_create_and_get_workflow():
    payload = {
        "goal": "Test API workflow creation",
        "nodes": [
            {"node_id": "step1", "goal": "Initialize", "action": {"type": "noop"}},
            {
                "node_id": "step2",
                "goal": "Process",
                "dependencies": ["step1"],
                "action": {"type": "noop"},
            },
        ],
        "auto_start": False,
    }

    create_res = client.post("/api/workflows", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    wf_id = data["workflow_id"]
    assert data["status"] == "READY"
    assert len(data["nodes"]) == 2

    # GET detail
    get_res = client.get(f"/api/workflows/{wf_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["workflow_id"] == wf_id
    assert detail["progress"]["total"] == 2


def test_api_list_workflows():
    res = client.get("/api/workflows?limit=10")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)


def test_api_stop_workflow():
    payload = {
        "goal": "Test API stop",
        "nodes": [{"node_id": "s1", "goal": "noop", "action": {"type": "noop"}}],
        "auto_start": True,
    }
    create_res = client.post("/api/workflows", json=payload)
    wf_id = create_res.json()["workflow_id"]

    stop_res = client.post(f"/api/workflows/{wf_id}/stop", json={"reason": "test stop"})
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "stopped"


def test_api_pause_and_resume():
    payload = {
        "goal": "Test API pause",
        "nodes": [{"node_id": "s1", "goal": "noop", "action": {"type": "noop"}}],
        "auto_start": True,
    }
    create_res = client.post("/api/workflows", json=payload)
    wf_id = create_res.json()["workflow_id"]

    # Pause
    pause_res = client.post(f"/api/workflows/{wf_id}/pause")
    assert pause_res.status_code in (200, 400)  # May complete quickly if noop

    # Resume if paused
    if pause_res.status_code == 200:
        resume_res = client.post(f"/api/workflows/{wf_id}/resume")
        assert resume_res.status_code == 200


def test_api_invalid_dag_rejected():
    # Cyclic DAG
    payload = {
        "goal": "Invalid DAG",
        "nodes": [
            {"node_id": "A", "goal": "A", "dependencies": ["B"]},
            {"node_id": "B", "goal": "B", "dependencies": ["A"]},
        ],
    }
    res = client.post("/api/workflows", json=payload)
    assert res.status_code == 400
    assert (
        "Circular" in res.json()["detail"]
        or "validation" in res.json()["detail"].lower()
    )
