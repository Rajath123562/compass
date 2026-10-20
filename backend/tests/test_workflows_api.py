"""
COMPASS Workflows Router & Orchestrator API Integration Tests (COMPASS-AUDIT-021)
Validates that the production API router correctly exercises the authoritative WorkflowOrchestrator.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_create_and_get_workflow_via_api():
    """Create a workflow with DAG nodes and retrieve its status through the production API."""
    payload = {
        "goal": "Test workflow DAG execution",
        "nodes": [
            {
                "node_id": "node-1",
                "goal": "First Step",
                "operation": "ui_action",
                "dependencies": [],
            },
            {
                "node_id": "node-2",
                "goal": "Second Step dependent on first",
                "operation": "ui_action",
                "dependencies": ["node-1"],
            },
        ],
        "auto_start": False,
    }

    create_resp = client.post("/api/workflows", json=payload)
    assert create_resp.status_code == 201
    wf_data = create_resp.json()
    wf_id = wf_data["workflow_id"]
    assert wf_id is not None
    assert len(wf_data["nodes"]) == 2

    # Query status
    get_resp = client.get(f"/api/workflows/{wf_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["workflow_id"] == wf_id


def test_workflow_stop_via_api():
    """Stop a workflow through the production API endpoint."""
    payload = {
        "goal": "Workflow to be stopped",
        "nodes": [
            {
                "node_id": "step-a",
                "goal": "Step A",
                "operation": "ui_action",
                "dependencies": [],
            }
        ],
        "auto_start": False,
    }

    create_resp = client.post("/api/workflows", json=payload)
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["workflow_id"]

    stop_resp = client.post(
        f"/api/workflows/{wf_id}/stop", json={"reason": "User stop via test"}
    )
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"].lower() == "stopped"
