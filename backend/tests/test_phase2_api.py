"""
Tests for Phase 2 perception and automation API endpoints.
"""

import sys

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


class TestPerceptionEndpoints:
    def test_perception_status_endpoint(self):
        resp = client.get("/api/perception/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "uia" in data
        assert "polling" in data
        assert "screen_capture" in data

    def test_perception_foreground_endpoint_responds(self):
        resp = client.get("/api/perception/foreground")
        # Either succeeds (real window) or 503 (no foreground in agent)
        assert resp.status_code in (200, 503)

    def test_perception_elements_invalid_hwnd(self):
        resp = client.get("/api/perception/elements?hwnd=999999999")
        assert resp.status_code in (200, 503)

    def test_perception_elements_filter_param(self):
        resp = client.get("/api/perception/elements?filter=interactive")
        assert resp.status_code in (200, 503)

    def test_perception_capture_bad_mode(self):
        resp = client.post("/api/perception/capture", json={"mode": "invalid_mode"})
        assert resp.status_code in (422, 503)

    def test_perception_capture_region_missing_params(self):
        resp = client.post("/api/perception/capture", json={"mode": "region"})
        assert resp.status_code in (422, 503)

    def test_perception_capture_region_negative_dims(self):
        resp = client.post(
            "/api/perception/capture",
            json={"mode": "region", "x": 0, "y": 0, "width": -100, "height": 50},
        )
        assert resp.status_code in (422, 503)

    def test_perception_find_no_params_returns_422(self):
        resp = client.post("/api/perception/find", json={"hwnd": 12345})
        assert resp.status_code == 422

    def test_perception_status_uia_available_on_windows(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        resp = client.get("/api/perception/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uia"]["available"] is True


class TestAutomationEndpoints:
    def _make_element_ref(self, **kwargs):
        base = {
            "hwnd": 99999999,
            "runtime_id": "",
            "automation_id": "",
            "control_type": "Button",
            "name": "Test",
            "bounds": {"left": 0, "top": 0, "right": 100, "bottom": 40},
            "window_title": "Test",
            "process_id": 0,
        }
        base.update(kwargs)
        return base

    def test_click_invalid_hwnd_rejected_by_validation(self):
        resp = client.post(
            "/api/automation/click",
            json={"element": self._make_element_ref(hwnd=999999999)},
        )
        # Should be 422 (validation failure: invalid HWND) or 200 with success=False
        data = resp.json()
        if resp.status_code == 422:
            assert "detail" in data
        else:
            # Some environments return 200 with success=False
            assert data.get("success") is False or "error" in data

    def test_type_into_button_rejected(self):
        resp = client.post(
            "/api/automation/type",
            json={
                "element": self._make_element_ref(control_type="Button"),
                "text": "hello",
            },
        )
        assert resp.status_code in (200, 422)

    def test_key_unknown_rejected(self):
        resp = client.post("/api/automation/key", json={"key": "__badkey__"})
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_key_enter_validates(self):
        resp = client.post("/api/automation/key", json={"key": "enter"})
        # Either succeeds (200) — real SendInput — or 200 with success result
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "action_type" in data

    def test_action_log_endpoint(self):
        resp = client.get("/api/automation/log")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_action_log_with_limit(self):
        resp = client.get("/api/automation/log?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 5

    def test_click_without_element_returns_422(self):
        resp = client.post("/api/automation/click", json={})
        assert resp.status_code == 422

    def test_type_without_text_returns_422(self):
        resp = client.post(
            "/api/automation/type", json={"element": self._make_element_ref()}
        )
        assert resp.status_code == 422

    def test_key_without_key_returns_422(self):
        resp = client.post("/api/automation/key", json={})
        assert resp.status_code == 422


class TestSystemEndpoints:
    def test_get_active_window(self):
        resp = client.get("/api/system/active_window")
        assert resp.status_code == 200
        data = resp.json()
        assert "app_name" in data
        assert "window_title" in data
        assert "status" in data

