"""
COMPASS Phase 6 — Loop and Oscillation Detector
Guarantees execution loop termination by detecting repeated action failures,
state oscillation cycles, and infinite replanning loops.
"""

from __future__ import annotations

import hashlib
from collections import deque
from typing import Any

from backend.app.logging_config import logger


class LoopDetectionError(RuntimeError):
    """Raised when an unrecoverable execution loop or oscillation is detected."""



class LoopDetector:
    """
    Tracks action and state history for a task to detect execution loops:
    1. Repeated action failures on the same target.
    2. State oscillation (A -> B -> A -> B).
    3. Repeated identical replans.
    """

    DEFAULT_MAX_REPEATED_ACTIONS = 3
    DEFAULT_MAX_STATE_OSCILLATIONS = 2
    DEFAULT_MAX_REPLANS = 3

    def __init__(
        self,
        max_repeated_actions: int = DEFAULT_MAX_REPEATED_ACTIONS,
        max_state_oscillations: int = DEFAULT_MAX_STATE_OSCILLATIONS,
        max_replans: int = DEFAULT_MAX_REPLANS,
    ):
        self.max_repeated_actions = max_repeated_actions
        self.max_state_oscillations = max_state_oscillations
        self.max_replans = max_replans

        self._action_history: list[dict[str, Any]] = []
        self._state_hashes: deque = deque(maxlen=20)
        self._replan_count: int = 0
        self._plan_hashes: list[str] = []

    def record_action_attempt(
        self, action_type: str, target_id: str, success: bool, verification_status: str
    ) -> tuple[bool, str | None]:
        """
        Record an action execution attempt and check if it forms a repeated failure loop.
        Returns (loop_detected, reason).
        """
        entry = {
            "action_type": action_type,
            "target_id": target_id or "unknown",
            "success": success,
            "verification_status": verification_status,
        }
        self._action_history.append(entry)

        # Check for consecutive failed attempts on same target
        consecutive_failures = 0
        for past in reversed(self._action_history):
            if (
                past["action_type"] == action_type
                and past["target_id"] == target_id
                and not past["success"]
            ):
                consecutive_failures += 1
                if consecutive_failures >= self.max_repeated_actions:
                    reason = f"Loop detected: action '{action_type}' failed {consecutive_failures} consecutive times on target '{target_id}'."
                    logger.error(reason)
                    return True, reason
            else:
                break

        return False, None

    def record_ui_state(self, state_summary: str) -> tuple[bool, str | None]:
        """
        Record observed UI state hash and detect oscillation cycles (A -> B -> A -> B).
        Returns (oscillation_detected, reason).
        """
        state_hash = hashlib.sha256(state_summary.encode("utf-8")).hexdigest()[:12]
        self._state_hashes.append(state_hash)

        # Check for 2-cycle oscillation (A, B, A, B)
        if len(self._state_hashes) >= 4:
            h = list(self._state_hashes)
            if h[-1] == h[-3] and h[-2] == h[-4] and h[-1] != h[-2]:
                reason = f"State oscillation cycle detected between states '{h[-1]}' and '{h[-2]}'."
                logger.error(reason)
                return True, reason

        # Check for 3-cycle oscillation (A, B, C, A, B, C)
        if len(self._state_hashes) >= 6:
            h = list(self._state_hashes)
            if h[-1] == h[-4] and h[-2] == h[-5] and h[-3] == h[-6]:
                reason = f"3-state oscillation cycle detected ({h[-1]} -> {h[-2]} -> {h[-3]})."
                logger.error(reason)
                return True, reason

        return False, None

    def record_replan(self, plan_hash: str) -> tuple[bool, str | None]:
        """
        Record a replan event. Rejects excessive replans or identical cyclic replans.
        Returns (loop_detected, reason).
        """
        self._replan_count += 1
        self._plan_hashes.append(plan_hash)

        if self._replan_count > self.max_replans:
            reason = f"Maximum replan limit ({self.max_replans}) exceeded without reaching terminal goal."
            logger.error(reason)
            return True, reason

        # Check if same plan hash was generated repeatedly
        if self._plan_hashes.count(plan_hash) >= 2:
            reason = (
                f"Cyclic replan detected: identical plan '{plan_hash}' regenerated."
            )
            logger.error(reason)
            return True, reason

        return False, None

    def reset(self) -> None:
        """Reset all tracking history for a fresh task."""
        self._action_history.clear()
        self._state_hashes.clear()
        self._replan_count = 0
        self._plan_hashes.clear()
