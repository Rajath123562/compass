"""
Unit tests for COMPASS configuration.
"""

from backend.app.config import Settings


def test_default_settings():
    s = Settings()
    assert s.app_name == "COMPASS"
    assert s.port == 8000
    assert s.host == "127.0.0.1"
    assert s.environment == "development"
    assert s.storage_dir.name == "storage"
    assert s.database_path.name == "compass.db"
    assert s.log_file.name == "compass.log"
    assert "http://localhost:5173" in s.allowed_origins
