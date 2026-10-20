from fastapi.testclient import TestClient

from backend.app.database import db
from backend.app.main import app

client = TestClient(app)


def test_reliability_health():
    response = client.get("/api/reliability/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "database" in data
    assert data["database"]["status"] == "healthy"


import uuid


def test_incident_creation_db():
    incident_id = f"inc_test_1_{uuid.uuid4().hex[:8]}"
    db.create_incident(
        {
            "incident_id": incident_id,
            "severity": "WARNING",
            "description": "Test incident",
        }
    )

    inc = db.get_incident(incident_id)
    assert inc is not None
    assert inc["severity"] == "WARNING"
    assert inc["status"] == "OPEN"
