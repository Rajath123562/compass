"""
COMPASS — OpenTelemetry Integration (Phase 14)
Structured tracing and metrics for the COMPASS lifecycle.

Provides decorators and context managers to trace:
TASK -> UNDERSTAND -> PERCEIVE -> PLAN -> VALIDATE -> SAFETY -> ACT -> VERIFY -> ADAPT

Ensures sensitive data (passwords, tokens, credentials) is NEVER logged.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Lazy imports
_otel_api = None
_otel_trace = None
_otel_metrics = None


def _ensure_otel():
    global _otel_api, _otel_trace, _otel_metrics
    if _otel_api is not None:
        return True
    try:
        from opentelemetry import metrics as otel_metrics
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.metrics import MeterProvider  # noqa: F401
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        _otel_trace = otel_trace
        _otel_metrics = otel_metrics

        # Setup basic provider if not already set
        if not isinstance(otel_trace.get_tracer_provider(), TracerProvider):
            resource = Resource.create({"service.name": "compass-engine"})
            provider = TracerProvider(resource=resource)
            otel_trace.set_tracer_provider(provider)

        _otel_api = True
        return True
    except ImportError:
        logger.warning("OpenTelemetry not installed, tracing disabled")
        return False


# Sensitive keys that must be redacted from telemetry attributes
_SENSITIVE_KEYS = re.compile(
    r"(password|secret|token|key|credential|auth|ssn|credit_card)", re.IGNORECASE
)


def _sanitize_attributes(attrs: dict[str, Any]) -> dict[str, str]:
    """Sanitize telemetry attributes to prevent logging sensitive data."""
    if not attrs:
        return {}
    sanitized = {}
    for k, v in attrs.items():
        if _SENSITIVE_KEYS.search(k):
            sanitized[k] = "[REDACTED]"
        else:
            # Convert to string to avoid complex type issues in OTel
            sanitized[k] = str(v)[:1000]  # Cap length for safety
    return sanitized


class CompassTracer:
    """Wrapper around OpenTelemetry for COMPASS lifecycle tracing."""

    def __init__(self, component_name: str = "compass"):
        self.component_name = component_name

    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        """Start a new trace span."""
        if not _ensure_otel():
            from contextlib import nullcontext

            return nullcontext()

        tracer = _otel_trace.get_tracer(self.component_name)
        safe_attrs = _sanitize_attributes(attributes or {})
        return tracer.start_as_current_span(name, attributes=safe_attrs)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None):
        """Add an event to the current span."""
        if not _ensure_otel():
            return

        span = _otel_trace.get_current_span()
        if span and span.is_recording():
            safe_attrs = _sanitize_attributes(attributes or {})
            span.add_event(name, attributes=safe_attrs)

    def record_exception(self, exception: Exception):
        """Record an exception on the current span."""
        if not _ensure_otel():
            return

        span = _otel_trace.get_current_span()
        if span and span.is_recording():
            span.record_exception(exception)
            span.set_status(_otel_trace.Status(_otel_trace.StatusCode.ERROR))


# Global tracer instance
tracer = CompassTracer()

F = TypeVar("F", bound=Callable[..., Any])


def trace_lifecycle(step_name: str) -> Callable[[F], F]:
    """
    Decorator to trace a COMPASS lifecycle step.
    (UNDERSTAND, PERCEIVE, PLAN, VALIDATE, SAFETY, ACT, VERIFY, ADAPT)
    """

    def decorator(func: F) -> F:
        def wrapper(*args, **kwargs):
            # Extract basic non-sensitive args for tracing if possible
            attrs = {"step": step_name}
            with tracer.start_span(
                f"compass.{step_name.lower()}", attributes=attrs
            ) as span:  # noqa: F841
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    tracer.record_exception(e)
                    raise

        return wrapper

    return decorator
