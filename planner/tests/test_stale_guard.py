"""
Unit tests for Multi-Factor Stale Observation Guard (Phase 4, Addendum §14, Directive §14).
Validates temporal age limits, sensitive thresholds, and target existence checks.
"""

import time

from planner.stale_guard import stale_guard


def test_stale_guard_fresh_observation():
    now = time.time()
    res = stale_guard.validate_freshness(
        observation_timestamp=now - 0.5,  # 500ms ago
        is_sensitive=False,
    )
    assert res.is_fresh is True
    assert res.stale_reason is None


def test_stale_guard_normal_expired_over_5000ms():
    now = time.time()
    res = stale_guard.validate_freshness(
        observation_timestamp=now - 5.5,  # 5500ms ago
        is_sensitive=False,
    )
    assert res.is_fresh is False
    assert "exceeds maximum freshness" in res.stale_reason


def test_stale_guard_sensitive_threshold_2000ms():
    """Directive §14: For sensitive actions, require stronger freshness (<= 2000ms)."""
    now = time.time()
    # 2500ms is fresh for normal (<=5000ms) but stale for sensitive (<=2000ms)
    res_normal = stale_guard.validate_freshness(
        observation_timestamp=now - 2.5, is_sensitive=False
    )
    assert res_normal.is_fresh is True

    res_sensitive = stale_guard.validate_freshness(
        observation_timestamp=now - 2.5, is_sensitive=True
    )
    assert res_sensitive.is_fresh is False
    assert "exceeds maximum freshness threshold 2000.0ms" in res_sensitive.stale_reason


def test_stale_guard_target_element_disappeared():
    now = time.time()
    res = stale_guard.validate_freshness(
        observation_timestamp=now - 0.1, live_element_exists=False
    )
    assert res.is_fresh is False
    assert "disappeared" in res.stale_reason


def test_stale_guard_bounds_drift_detected():
    """Directive §14: Invalidate observation if element bounds have drifted beyond tolerance."""
    orig_bounds = {"left": 100, "top": 100, "right": 200, "bottom": 150}
    drifted_bounds = {
        "left": 130,
        "top": 100,
        "right": 230,
        "bottom": 150,
    }  # 30px shift > 15px tol
    assert (
        stale_guard.has_bounds_drifted(orig_bounds, drifted_bounds, tolerance_px=15.0)
        is True
    )

    # Within tolerance
    close_bounds = {
        "left": 105,
        "top": 102,
        "right": 205,
        "bottom": 152,
    }  # 5px shift <= 15px tol
    assert (
        stale_guard.has_bounds_drifted(orig_bounds, close_bounds, tolerance_px=15.0)
        is False
    )


def test_stale_guard_dead_hwnd_detected():
    """Directive §14: Invalidate observation if target window HWND is closed/dead."""
    now = time.time()
    res = stale_guard.validate_freshness(
        observation_timestamp=now - 0.1,
        target_hwnd=999999999,  # Non-existent HWND
    )
    assert res.is_fresh is False
    assert "closed or destroyed" in res.stale_reason


def test_stale_guard_element_disabled():
    """Directive §22: Invalidate observation if target element became disabled."""
    now = time.time()
    res = stale_guard.validate_freshness(
        observation_timestamp=now - 0.1, live_element_enabled=False
    )
    assert res.is_fresh is False
    assert "disabled" in res.stale_reason.lower()


def test_stale_guard_element_invisible():
    """Directive §22: Invalidate observation if target element is no longer visible."""
    now = time.time()
    res = stale_guard.validate_freshness(
        observation_timestamp=now - 0.1, live_element_visible=False
    )
    assert res.is_fresh is False
    assert "visible" in res.stale_reason.lower()
