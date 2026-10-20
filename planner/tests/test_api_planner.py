"""
Integration tests for Phase 3 Planner and AI Endpoints.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_service import task_service

client = TestClient(app)


class TestPlannerAPI:
    def test_get_ai_status(self):
        resp = client.get("/api/ai/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "free_only_policy" in data
        assert data["free_only_policy"] is True
        assert "hardware" in data
        assert data["hardware"] is not None

    def test_get_ai_models_free_only(self):
        resp = client.get("/api/ai/models?free_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "free_only_filter" in data
        assert data["free_only_filter"] is True
        # Every model returned under free_only must have is_free=True
        for m in data["models"]:
            assert m["is_free"] is True

    def test_run_task_endpoint(self, monkeypatch):
        monkeypatch.setattr(
            "backend.app.routers.planner.execution_engine.run_task",
            lambda **kw: {"success": True},
        )
        task = task_service.create_task("Run API Test")
        task_id = task["id"]

        resp = client.post(f"/api/tasks/{task_id}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["task_id"] == task_id

    def test_stop_task_endpoint(self):
        task = task_service.create_task("Stop API Test")
        task_id = task["id"]

        resp = client.post(f"/api/tasks/{task_id}/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task_id
        assert data["state"] == "STOPPED"

    def test_get_task_state_endpoint(self):
        task = task_service.create_task("State API Test")
        task_id = task["id"]

        resp = client.get(f"/api/tasks/{task_id}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task_id
        assert "is_stopped" in data
        assert "events" in data

    def test_plan_requires_valid_goal(self):
        # Goal too short
        resp = client.post("/api/planner/plan", json={"goal": "a"})
        assert resp.status_code == 422

    def test_get_gemini_status(self):
        resp = client.get("/api/ai/gemini_status")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data
        assert "is_configured" in data
        assert "budget" in data

    def test_update_gemini_config(self):
        resp = client.post("/api/ai/gemini_config", json={"api_key": "test-key-mock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["is_configured"] is True

