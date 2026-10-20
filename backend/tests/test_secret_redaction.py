"""
Unit tests for SecretRedactionFilter in logging configuration (§14).
Validates that Bearer tokens, API keys, and passwords are scrubbed before logging.
"""

import logging

from backend.app.logging_config import SecretRedactionFilter


def test_bearer_token_redacted():
    filter_obj = SecretRedactionFilter()
    msg = "Sending authorization: Bearer sk-ant-api03-abcdef1234567890 to endpoint"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert "sk-ant-api03" not in record.msg
    assert "Bearer [REDACTED]" in record.msg


def test_api_key_redacted():
    filter_obj = SecretRedactionFilter()
    msg = "Connecting with api_key=AIzaSyD-1234567890abcdef and secret: 'SuperSecretToken123'"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert "AIzaSyD-1234567890abcdef" not in record.msg
    assert "SuperSecretToken123" not in record.msg
    assert "[REDACTED]" in record.msg


def test_password_redacted():
    filter_obj = SecretRedactionFilter()
    msg = "Database auth failed for user admin with password='Password123!'"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert "Password123!" not in record.msg
    assert "[REDACTED]" in record.msg


def test_non_secret_text_preserved():
    filter_obj = SecretRedactionFilter()
    msg = "Task task_12345 transitioned to state PLANNING for goal 'Open Notepad and type text'"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert record.msg == msg
