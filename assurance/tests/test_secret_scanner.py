"""
COMPASS Secret Scanner Tests (COMPASS-AUDIT-015)
Tests coverage of dotfiles, assurance directory, and elimination of broad generic-word suppression.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from assurance.tools.secret_scanner import scan_file, should_scan_file


def test_dotfile_env_is_scanned():
    """Exact .env and .env.production files must be accepted for scanning."""
    assert should_scan_file(Path(".env")) is True
    assert should_scan_file(Path(".env.production")) is True
    assert should_scan_file(Path("config.json")) is True


def test_secret_in_dotfile_detected(tmp_path):
    """Credentials in .env files must be flagged and redacted."""
    env_file = tmp_path / ".env"
    # An API key pattern with a non-dummy key
    env_file.write_text("API_KEY='live_prod_abcdef12345678901234567890'\n", encoding="utf-8")

    with patch("assurance.tools.secret_scanner.ROOT_DIR", tmp_path):
        findings, fps = scan_file(env_file)

    assert len(findings) == 1
    assert findings[0]["secret_type"] == "Generic API Key"
    # Ensure raw secret is scrubbed from evidence
    assert "live_prod_" not in findings[0]["evidence"]
    assert "[REDACTED_GENERIC_API_KEY]" in findings[0]["evidence"]


def test_secret_not_suppressed_by_generic_words_on_same_line(tmp_path):
    """A secret on a line that also contains the word 'test' or 'payload' must NOT be suppressed."""
    py_file = tmp_path / "app_config.py"
    py_file.write_text(
        "secret_key = 'live_prod_abcdef12345678901234567890' # This is for payload test run\n",
        encoding="utf-8",
    )

    with patch("assurance.tools.secret_scanner.ROOT_DIR", tmp_path):
        findings, fps = scan_file(py_file)

    assert len(findings) == 1
    assert findings[0]["secret_type"] == "Generic Secret Key"
    assert "live_prod_" not in findings[0]["evidence"]
