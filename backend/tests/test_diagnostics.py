"""
Unit tests for COMPASS Zero-Knowledge Diagnostic Scrubber & Diagnostics API.
"""

import getpass

from fastapi.testclient import TestClient

from backend.app.main import app
from scripts.export_diagnostic_bundle import (
    generate_diagnostic_bundle,
    redact_pii,
    sanitize_dict,
)

client = TestClient(app)


def test_redact_pii_scrubbing():
    user = getpass.getuser()
    sample = f"User {user} logged in from C:\\Users\\{user}\\Documents\\test.txt with email secret@corp.com and token Bearer dummy_abcdef1234567890abcdef1234567890"
    cleaned = redact_pii(sample)

    assert user not in cleaned or user == "<USER>"
    assert "<USER>" in cleaned
    assert "<EMAIL>" in cleaned
    assert "<REDACTED_SECRET>" in cleaned
    assert "secret@corp.com" not in cleaned


def test_sanitize_dict_recursive():
    user = getpass.getuser()
    data = {
        "user_path": f"C:\\Users\\{user}\\AppData",
        "nested": {
            "email": "test@test.com",
            "count": 42,
        },
    }
    cleaned = sanitize_dict(data)
    assert cleaned["nested"]["email"] == "<EMAIL>"
    assert cleaned["nested"]["count"] == 42
    assert "<USER>" in cleaned["user_path"]


def test_generate_diagnostic_bundle_structure(tmp_path):
    target = tmp_path / "diagnostics_test.json"
    bundle = generate_diagnostic_bundle(output_file=target, create_zip=True)

    assert bundle["status"] == "success"
    assert bundle["redaction_verified"] is True
    assert "system" in bundle
    assert "database" in bundle
    assert "ports" in bundle
    assert "sha256_checksum" in bundle
    assert target.exists()

    # Verify zip archive
    zip_path = target.with_suffix(".zip")
    assert zip_path.exists()


def test_api_diagnostics_endpoint():
    res = client.get("/api/system/diagnostics")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["redaction_verified"] is True
    assert "system" in data
    assert "database" in data
