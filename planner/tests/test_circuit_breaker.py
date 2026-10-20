"""
Unit tests for COMPASS Circuit Breaker (§17).
Validates CLOSED -> OPEN -> HALF_OPEN -> CLOSED transitions and fail-fast behavior.
"""

import time

from planner.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_initial_state_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=1.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=1.0)
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_resets_failure_count_on_success():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=1.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    # Need 3 more failures to trip
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_circuit_half_opens_after_recovery_timeout():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN


def test_circuit_closes_on_success_in_half_open():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=0.1)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_reopens_on_failure_in_half_open():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=0.1)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False
