"""
COMPASS Local API Trust Boundary Regression Tests (COMPASS-AUDIT-016)
Tests origin header validation, CORS configuration, and local control protection.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_allowed_origin_is_accepted():
    """Requests from configured frontend origin http://localhost:5173 are permitted."""
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_native_client_without_origin_header_is_accepted():
    """Desktop apps or local scripts without Origin header must continue to function normally."""
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_malicious_foreign_browser_origin_is_blocked():
    """Untrusted web origins attempting to hit local API control endpoints receive 403 Forbidden."""
    resp = client.post(
        "/api/tasks",
        json={"goal": "Malicious goal from external website"},
        headers={"Origin": "https://attacker-controlled-site.com"},
    )
    assert resp.status_code == 403
    assert "not authorized" in resp.json().get("detail", "").lower()


def test_cors_preflight_does_not_return_wildcard_with_credentials():
    """Preflight OPTIONS request from allowed origin returns specific origin, not '*'."""
    resp = client.options(
        "/api/tasks",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("access-control-allow-origin") != "*"
