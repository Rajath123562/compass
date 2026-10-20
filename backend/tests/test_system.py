"""
Tests for COMPASS /api/system endpoints.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_system_info():
    resp = client.get("/api/system/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "os" in data
    assert "python_version" in data
    assert "cpu_percent" in data
    assert "memory_used_mb" in data
    assert "process_pid" in data
    assert data["process_pid"] > 0


def test_shutdown_remote_host_rejected():
    # TestClient by default sends testclient host; pass remote client
    remote_client = TestClient(
        app, base_url="http://testserver", client=("192.168.1.100", 50000)
    )
    resp = remote_client.post("/api/system/shutdown")
    assert resp.status_code == 403
    assert "restricted to localhost" in resp.json()["detail"].lower()
