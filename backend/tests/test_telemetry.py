"""
COMPASS — OpenTelemetry Tests
Tests for backend/app/telemetry.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.telemetry import (
    CompassTracer,
    _sanitize_attributes,
    trace_lifecycle,
)


class TestAttributeSanitization:
    def test_sanitizes_passwords(self):
        attrs = {
            "user": "admin",
            "password": "supersecretpassword",
            "PASSWORD_HASH": "123",
        }
        clean = _sanitize_attributes(attrs)
        assert clean["user"] == "admin"
        assert clean["password"] == "[REDACTED]"
        assert clean["PASSWORD_HASH"] == "[REDACTED]"

    def test_sanitizes_tokens(self):
        attrs = {"api_token": "sk-12345", "Auth-Token": "Bearer xyz"}
        clean = _sanitize_attributes(attrs)
        assert clean["api_token"] == "[REDACTED]"
        assert clean["Auth-Token"] == "[REDACTED]"

    def test_truncates_long_strings(self):
        long_str = "A" * 2000
        attrs = {"long_field": long_str}
        clean = _sanitize_attributes(attrs)
        assert len(clean["long_field"]) == 1000

    def test_converts_types_to_string(self):
        attrs = {"count": 42, "is_active": True}
        clean = _sanitize_attributes(attrs)
        assert clean["count"] == "42"
        assert clean["is_active"] == "True"


class TestCompassTracer:
    def test_start_span(self):
        tracer = CompassTracer()
        # Should run without raising even if OTel not fully configured
        with tracer.start_span("test_span", {"key": "val"}) as span:  # noqa: F841
            pass

    def test_add_event(self):
        tracer = CompassTracer()
        with tracer.start_span("test_span") as span:  # noqa: F841
            tracer.add_event("test_event", {"info": "data"})

    def test_record_exception(self):
        tracer = CompassTracer()
        with tracer.start_span("test_span") as span:  # noqa: F841
            try:
                raise ValueError("test error")
            except Exception as e:  # noqa: BLE001
                tracer.record_exception(e)


class TestTraceLifecycleDecorator:
    def test_decorator_success(self):
        @trace_lifecycle("TEST_STEP")
        def my_func(x):
            return x * 2

        assert my_func(5) == 10

    def test_decorator_exception(self):
        @trace_lifecycle("TEST_STEP")
        def my_func():
            raise RuntimeError("Failure")

        with pytest.raises(RuntimeError):
            my_func()
