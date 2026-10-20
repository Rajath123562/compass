"""
Integration tests for Phase 4 API Endpoints.
Validates goal understanding, confirmation, timeline, mode switching, and resource telemetry routes.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_service import task_service
from planner.human_approval import human_approval_controller
from planner.models import ConfidenceLevel, Decision, PlannerActionType, RiskLevel

client = TestClient(app)


def test_api_goal_understand():
    response = client.post(
        "/api/planner/goal/understand",
        json={"goal": "Open Notepad and type test message"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_application"] == "Notepad"
    assert data["is_ambiguous"] is False
    assert "text_input" in data["required_capabilities"]


def test_api_guidance_mode_get_and_set():
    # Get current mode
    get_res = client.get("/api/planner/mode")
    assert get_res.status_code == 200
    assert "mode" in get_res.json()

    # Set mode to CONFIRM
    post_res = client.post("/api/planner/mode", json={"mode": "CONFIRM"})
    assert post_res.status_code == 200
    assert post_res.json()["mode"] == "CONFIRM"

    # Reset to ASSIST
    client.post("/api/planner/mode", json={"mode": "ASSIST"})


def test_api_confirm_action():
    task = task_service.create_task("Confirm API Test")
    tid = task["id"]
    dec = Decision(
        decision_id="dec_api_001",
        task_id=tid,
        observation_id="obs_001",
        action=PlannerActionType.CLICK,
        target_description="Delete File",
        confidence=ConfidenceLevel.HIGH,
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True,
        human_explanation="Click delete",
    )
    human_approval_controller.create_approval_request(dec)

    # Approve via API
    resp = client.post(
        f"/api/planner/confirm/{tid}",
        json={"decision_id": "dec_api_001", "approved": True},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "GRANTED"


def test_api_get_timeline():
    task = task_service.create_task("Timeline API Test")
    tid = task["id"]
    resp = client.get(f"/api/planner/timeline/{tid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == tid
    assert "timeline" in data


def test_api_resources_endpoint():
    resp = client.get("/api/planner/resources")
    assert resp.status_code == 200
    data = resp.json()
    assert "compass_backend_rss_mb" in data
    assert "system_ram_total_mb" in data
    assert "is_within_budget" in data


def test_api_confirm_nonexistent_task_returns_404():
    """Directive §33: Confirming an action on non-existent task returns 404."""
    resp = client.post(
        "/api/planner/confirm/non_existent_task",
        json={"decision_id": "dec_none", "approved": True},
    )
    assert resp.status_code == 404


def test_api_confirm_nonexistent_decision_returns_404():
    """Directive §33: Confirming non-existent decision returns 404."""
    task = task_service.create_task("Test 404 decision")
    resp = client.post(
        f"/api/planner/confirm/{task['id']}",
        json={"decision_id": "dec_does_not_exist", "approved": True},
    )
    assert resp.status_code == 404


def test_api_confirm_terminal_task_returns_409():
    """Directive §33: Confirming action on a completed/terminal task returns 409."""
    from backend.app.models import TaskState

    task = task_service.create_task("Test terminal confirm")
    tid = task["id"]
    task_service.transition_state(tid, TaskState.PLANNING)
    task_service.transition_state(tid, TaskState.VALIDATING)
    task_service.transition_state(tid, TaskState.EXECUTING)
    task_service.transition_state(tid, TaskState.VERIFYING)
    task_service.transition_state(tid, TaskState.COMPLETED)

    resp = client.post(
        f"/api/planner/confirm/{tid}", json={"decision_id": "dec_any", "approved": True}
    )
    assert resp.status_code == 409


def test_api_confirm_consumed_approval_returns_409():
    """Directive §4, §9, §33: Re-confirming a consumed approval returns 409."""
    task = task_service.create_task("Test consumed approval")
    tid = task["id"]
    dec = Decision(
        decision_id="dec_api_consumed_001",
        task_id=tid,
        observation_id="obs_001",
        action=PlannerActionType.CLICK,
        target_description="Delete File",
        confidence=ConfidenceLevel.HIGH,
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True,
        human_explanation="Click delete",
    )
    human_approval_controller.create_approval_request(dec)
    human_approval_controller.grant_approval(tid, dec.decision_id)
    human_approval_controller.consume_approval(tid, dec.decision_id)

    resp = client.post(
        f"/api/planner/confirm/{tid}",
        json={"decision_id": dec.decision_id, "approved": True},
    )
    assert resp.status_code == 409
