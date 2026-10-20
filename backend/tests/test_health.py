"""
Tests for COMPASS /api/health endpoint.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "COMPASS"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0

    # Real database checks
    assert "database" in data
    assert data["database"]["status"] == "healthy"
    assert data["database"]["journal_mode"].lower() == "wal"
    assert "task_count" in data["database"]

    # System stats
    assert "system" in data
    assert "memory_rss_mb" in data["system"]
    assert "cpu_percent" in data["system"]
    assert "disk_free_gb" in data["system"]
