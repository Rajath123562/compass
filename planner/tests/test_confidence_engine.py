"""
Unit tests for Evidence-Based Confidence Engine (Phase 4, Addendum §4, Directive §7).
Validates multi-signal evaluation and confidence degradation under conflicting evidence.
"""

from planner.confidence_engine import confidence_engine
from planner.models import ConfidenceLevel, TargetReference


def test_confidence_strong_match_with_active_window():
    ref = TargetReference(name="Save", automation_id="btn_save", hwnd=100)
    element = {
        "name": "Save",
        "automation_id": "btn_save",
        "hwnd": 100,
        "is_enabled": True,
        "bounds": {"left": 10, "top": 10, "width": 80, "height": 30},
    }
    active_win = {"hwnd": 100, "title": "Notepad"}

    res = confidence_engine.evaluate_confidence(
        target_ref=ref,
        element_snapshot=element,
        active_window=active_win,
        observation_age_ms=100.0,
    )
    assert res.level == ConfidenceLevel.HIGH
    assert res.score >= 0.85
    assert res.conflict_detected is False


def test_confidence_conflicting_evidence_degrades():
    """
    Directive §7: If vision says 'Button A' but UI Automation says 'Button B',
    confidence must decrease.
    """
    ref = TargetReference(name="Button B", hwnd=100)
    element = {
        "name": "Button B",
        "hwnd": 100,
        "is_enabled": True,
        "bounds": {"left": 10, "top": 10, "width": 80, "height": 30},
    }
    active_win = {"hwnd": 100}
    visual_evidence = {"text": "Button A"}  # Contradiction!

    res = confidence_engine.evaluate_confidence(
        target_ref=ref,
        element_snapshot=element,
        active_window=active_win,
        observation_age_ms=100.0,
        visual_evidence=visual_evidence,
    )
    assert res.conflict_detected is True
    assert res.level in [ConfidenceLevel.LOW, ConfidenceLevel.UNKNOWN]
    assert res.score <= 0.45


def test_confidence_missing_element_returns_unknown():
    ref = TargetReference(name="NonExistentButton")
    res = confidence_engine.evaluate_confidence(target_ref=ref, element_snapshot=None)
    assert res.level == ConfidenceLevel.UNKNOWN
    assert res.score == 0.0


def test_confidence_disabled_element_penalized():
    ref = TargetReference(name="Submit")
    element = {
        "name": "Submit",
        "hwnd": 100,
        "is_enabled": False,  # Disabled!
        "bounds": {"left": 10, "top": 10, "width": 80, "height": 30},
    }
    res = confidence_engine.evaluate_confidence(
        target_ref=ref, element_snapshot=element
    )
    assert "disabled_penalty" in res.signals
    assert res.score < 0.6
