"""
Unit tests for Coordinate Safety, DPI & Bounds Validation (Phase 4, Addendum §15, §16, Directive §15).
"""

from automation.safety import check_coordinates_safe


def test_coordinate_safety_valid():
    res = check_coordinates_safe(
        x=200, y=200, bounds={"left": 150, "top": 180, "width": 100, "height": 40}
    )
    assert res.ok is True


def test_coordinate_safety_reject_impossible_rectangle():
    """Reject zero or negative width/height."""
    res_zero_w = check_coordinates_safe(
        x=100, y=100, bounds={"left": 100, "top": 100, "width": 0, "height": 50}
    )
    assert res_zero_w.ok is False
    assert "Impossible" in res_zero_w.reason

    res_neg_h = check_coordinates_safe(
        x=100, y=100, bounds={"left": 100, "top": 100, "width": 50, "height": -10}
    )
    assert res_neg_h.ok is False
    assert "Impossible" in res_neg_h.reason


def test_coordinate_safety_reject_offscreen_impossible_coords():
    """Reject coordinates far outside monitor bounds."""
    res_offscreen = check_coordinates_safe(
        x=999999,
        y=999999,
        bounds={"left": 999900, "top": 999900, "width": 100, "height": 100},
    )
    assert res_offscreen.ok is False
    assert (
        "outside virtual screen" in res_offscreen.reason
        or "outside" in res_offscreen.reason.lower()
    )


def test_coordinate_safety_reject_negative_coordinates():
    res_neg = check_coordinates_safe(x=-5000, y=-5000)
    assert res_neg.ok is False
