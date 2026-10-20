"""
COMPASS Circuit Breaker Pattern (§17)
Protects against cascading AI provider failures and infinite retry loops.
Transitions between CLOSED, OPEN, and HALF_OPEN states.
"""

from __future__ import annotations

import threading
import time
from enum import Enum

from backend.app.logging_config import logger


class CircuitState(str, Enum):
    CLOSED = "CLOSED"  # Normal operation: requests allowed
    OPEN = "OPEN"  # Provider marked unavailable: requests rejected immediately
    HALF_OPEN = "HALF_OPEN"  # Trial probe: allowing test request to verify recovery


class CircuitBreaker:
    """
    Thread-safe circuit breaker for AI provider requests.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout_s: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._evaluate_state()
            return self._state

    def _evaluate_state(self) -> None:
        """Evaluate if OPEN circuit has elapsed recovery window."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self._recovery_timeout_s:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    f"CircuitBreaker state transitioned from OPEN to HALF_OPEN after {elapsed:.1f}s."
                )

    def can_execute(self) -> bool:
        """
        Check if request is allowed to execute.
        Returns False immediately if circuit is OPEN.
        """
        with self._lock:
            self._evaluate_state()
            if self._state == CircuitState.OPEN:  # noqa: SIM103
                return False
            return True

    def record_success(self) -> None:
        """Record successful provider response."""
        with self._lock:
            old_state = self._state
            self._consecutive_failures = 0
            self._state = CircuitState.CLOSED
            if old_state != CircuitState.CLOSED:
                logger.info(
                    f"CircuitBreaker recovered: state transitioned from {old_state.value} to CLOSED."
                )

    def record_failure(self) -> None:
        """Record provider failure/timeout."""
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "CircuitBreaker trial failed in HALF_OPEN: immediately returned to OPEN."
                )
            elif self._consecutive_failures >= self._failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"CircuitBreaker tripped to OPEN after {self._consecutive_failures} consecutive failures. "
                    f"Provider blocked for {self._recovery_timeout_s}s."
                )

    def reset(self) -> None:
        """Manual reset to initial CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._last_failure_time = 0.0


# Global singleton circuit breaker for AI provider (fast recovery for local models)
import os

ai_circuit_breaker = CircuitBreaker(
    failure_threshold=int(os.environ.get("COMPASS_CIRCUIT_FAILURE_THRESHOLD", "5")),
    recovery_timeout_s=float(os.environ.get("COMPASS_CIRCUIT_RECOVERY_S", "10.0")),
)
