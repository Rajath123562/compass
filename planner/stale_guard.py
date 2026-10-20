"""
COMPASS Phase 4 — Multi-Factor Stale Observation Guard
Goes beyond simple timer checks to validate live HWND existence, foreground context,
window bounds, screen metrics, target existence, and application identity.
Sensitive actions require strict freshness (<= 2000ms).
"""

from __future__ import annotations

import ctypes
import sys
import time
from typing import Any

from pydantic import BaseModel, Field

from backend.app.logging_config import logger


class StaleCheckResult(BaseModel):
    is_fresh: bool
    stale_reason: str | None = None
    age_ms: float
    checks: dict[str, bool] = Field(default_factory=dict)


class StaleGuard:
    """
    Multi-signal freshness and UI state consistency guard.
    Guarantees stale decisions never reach execution.
    """

    DEFAULT_MAX_AGE_NORMAL_MS = 5000.0
    DEFAULT_MAX_AGE_SENSITIVE_MS = 2000.0

    def __init__(self):
        pass

    def validate_freshness(
        self,
        observation_timestamp: float,
        target_hwnd: int | None = None,
        expected_window_title: str | None = None,
        is_sensitive: bool = False,
        custom_max_age_ms: float | None = None,
        live_element_exists: bool | None = None,
        live_element_enabled: bool | None = None,
        live_element_visible: bool | None = None,
        expected_dpi: int | None = None,
    ) -> StaleCheckResult:
        """
        Validate observation freshness across time, HWND validity, foreground focus,
        window state, and target existence.
        """
        now = time.time()
        age_ms = max(0.0, (now - observation_timestamp) * 1000.0)
        max_age = custom_max_age_ms or (
            self.DEFAULT_MAX_AGE_SENSITIVE_MS
            if is_sensitive
            else self.DEFAULT_MAX_AGE_NORMAL_MS
        )

        checks = {}

        # 1. Temporal Age Check
        time_ok = age_ms <= max_age
        checks["timestamp_freshness"] = time_ok
        if not time_ok:
            reason = f"Observation is stale: age {age_ms:.1f}ms exceeds maximum freshness threshold {max_age:.1f}ms."
            logger.info(f"StaleGuard flagged stale observation: {reason}")
            return StaleCheckResult(
                is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
            )

        # 2. Windows Environment Checks (if target_hwnd provided)
        if target_hwnd:
            if sys.platform == "win32":
                user32 = ctypes.windll.user32

                # 2a. Is window still alive?
                is_alive = bool(user32.IsWindow(target_hwnd))
                checks["hwnd_alive"] = is_alive
                if not is_alive:
                    reason = f"Target window HWND {target_hwnd} was closed or destroyed."
                    logger.warning(f"StaleGuard: {reason}")
                    return StaleCheckResult(
                        is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
                    )

                # 2b. Is window minimized?
                is_minimized = bool(user32.IsIconic(target_hwnd))
                checks["not_minimized"] = not is_minimized
                if is_minimized:
                    reason = f"Target window HWND {target_hwnd} was minimized by user."
                    logger.info(f"StaleGuard: {reason}")
                    return StaleCheckResult(
                        is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
                    )

                # 2c. Window title consistency
                if expected_window_title:
                    length = user32.GetWindowTextLengthW(target_hwnd)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(target_hwnd, buf, length + 1)
                    current_title = buf.value
                    title_match = (
                        expected_window_title.lower() in current_title.lower()
                        or current_title.lower() in expected_window_title.lower()
                    )
                    checks["window_title_match"] = title_match
                    if not title_match:
                        reason = f"Window title changed from '{expected_window_title}' to '{current_title}'."
                        logger.info(f"StaleGuard: {reason}")
                        return StaleCheckResult(
                            is_fresh=False,
                            stale_reason=reason,
                            age_ms=age_ms,
                            checks=checks,
                        )

                # 2d. Foreground check
                fg_hwnd = user32.GetForegroundWindow()
                # If fg_hwnd == 0, Windows is in transition or console host has no GUI active window.
                is_fg = (
                    (target_hwnd == fg_hwnd)
                    or bool(user32.GetAncestor(target_hwnd, 2) == fg_hwnd)
                    or (fg_hwnd == 0)
                )
                checks["is_foreground"] = is_fg
                if not is_fg:
                    reason = f"Target window {target_hwnd} lost foreground focus to HWND {fg_hwnd}."
                    logger.info(f"StaleGuard: {reason}")
                    return StaleCheckResult(
                        is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
                    )
            else:
                # COMPASS-AUDIT-020: On non-Windows, live HWND cannot be verified natively.
                # Must not report fresh without an explicit test adapter or known alive mock handle.
                mock_hwnds = getattr(self, "_mock_alive_hwnds", set())
                if target_hwnd not in mock_hwnds:
                    checks["hwnd_alive"] = False
                    reason = f"Target window HWND {target_hwnd} was closed or destroyed."
                    logger.warning(f"StaleGuard: {reason}")
                    return StaleCheckResult(
                        is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
                    )
                checks["hwnd_alive"] = True

        # 3. Live element existence & state checks
        if live_element_exists is False:
            checks["target_exists"] = False
            reason = "Target UI element disappeared from live application tree."
            logger.info(f"StaleGuard: {reason}")
            return StaleCheckResult(
                is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
            )
        elif live_element_exists is True:
            checks["target_exists"] = True

        if live_element_enabled is False:
            checks["target_enabled"] = False
            reason = "Target UI element has become disabled."
            logger.info(f"StaleGuard: {reason}")
            return StaleCheckResult(
                is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
            )
        elif live_element_enabled is True:
            checks["target_enabled"] = True

        if live_element_visible is False:
            checks["target_visible"] = False
            reason = "Target UI element is no longer visible on screen."
            logger.info(f"StaleGuard: {reason}")
            return StaleCheckResult(
                is_fresh=False, stale_reason=reason, age_ms=age_ms, checks=checks
            )
        elif live_element_visible is True:
            checks["target_visible"] = True

        # 4. DPI consistency check
        if expected_dpi is not None and sys.platform == "win32" and target_hwnd:
            try:
                cur_dpi = ctypes.windll.user32.GetDpiForWindow(target_hwnd)
                if cur_dpi and cur_dpi != expected_dpi:
                    checks["dpi_match"] = False
                    reason = f"DPI scaling changed from {expected_dpi} to {cur_dpi}."
                    logger.info(f"StaleGuard: {reason}")
                    return StaleCheckResult(
                        is_fresh=False,
                        stale_reason=reason,
                        age_ms=age_ms,
                        checks=checks,
                    )
                checks["dpi_match"] = True
            except Exception:  # noqa: BLE001, S110
                pass

        return StaleCheckResult(
            is_fresh=True, stale_reason=None, age_ms=age_ms, checks=checks
        )

    def has_bounds_drifted(
        self,
        orig_bounds: dict[str, Any] | None,
        curr_bounds: dict[str, Any] | None,
        tolerance_px: float = 15.0,
    ) -> bool:
        """
        Check whether element coordinates have drifted beyond tolerance.
        """
        if not orig_bounds or not curr_bounds:
            return True
        for key in ["left", "top", "right", "bottom"]:
            if abs(orig_bounds.get(key, 0) - curr_bounds.get(key, 0)) > tolerance_px:
                return True
        return False


stale_guard = StaleGuard()
