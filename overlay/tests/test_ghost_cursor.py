"""
Unit tests for Ghost Cursor, Bezier motion, and Neon visual guidance.
"""

import time
from unittest.mock import MagicMock

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

from overlay.ghost_cursor import (
    NEON_AMBER,
    NEON_CYAN,
    NEON_EMERALD,
    NEON_ROSE,
    GhostCursorController,
    Point2D,
    cubic_bezier_point,
    ease_in_out_cubic,
)
from overlay.renderer import OverlayRenderer


class TestGhostCursorBezier:
    """Test cubic Bezier curves and easing functions."""

    def test_cubic_bezier_endpoints(self):
        p0 = Point2D(0.0, 0.0)
        p1 = Point2D(20.0, 50.0)
        p2 = Point2D(80.0, 50.0)
        p3 = Point2D(100.0, 100.0)

        start = cubic_bezier_point(p0, p1, p2, p3, 0.0)
        assert start.x == 0.0
        assert start.y == 0.0

        end = cubic_bezier_point(p0, p1, p2, p3, 1.0)
        assert end.x == 100.0
        assert end.y == 100.0

        mid = cubic_bezier_point(p0, p1, p2, p3, 0.5)
        assert 0.0 < mid.x < 100.0
        assert 0.0 < mid.y < 100.0

    def test_ease_in_out_cubic(self):
        assert ease_in_out_cubic(0.0) == 0.0
        assert ease_in_out_cubic(1.0) == 1.0
        assert ease_in_out_cubic(0.5) == 0.5


class TestGhostCursorController:
    """Test GhostCursorController state updates, trails, and colors."""

    def test_start_motion_and_update(self):
        ctrl = GhostCursorController(duration_ms=100.0)
        ctrl.start_motion(
            from_x=0.0,
            from_y=0.0,
            to_x=500.0,
            to_y=500.0,
            action_type="click",
            tooltip="Click here",
            step_label="Step 1",
        )
        assert ctrl.state.is_animating is True
        assert ctrl.state.target_x == 500.0
        assert ctrl.state.target_y == 500.0

        # Step update
        st = ctrl.update()
        assert st.progress >= 0.0
        assert len(st.trail) >= 1

    def test_action_color_mapping(self):
        ctrl = GhostCursorController()
        ctrl.state.action_type = "click"
        assert ctrl.get_action_color() == NEON_CYAN

        ctrl.state.action_type = "type"
        assert ctrl.get_action_color() == NEON_EMERALD

        ctrl.state.action_type = "scroll"
        assert ctrl.get_action_color() == NEON_AMBER

        ctrl.state.action_type = "confirm"
        assert ctrl.get_action_color() == NEON_ROSE

    def test_idle_pulse_calculation(self):
        ctrl = GhostCursorController()
        ctrl.state.is_animating = False
        st = ctrl.update()
        assert st.pulse_radius > 0.0
        assert 0.0 <= st.pulse_alpha <= 1.0


class TestOverlayRendererGhostCursor:
    """Test OverlayRenderer painting with GhostCursor attached."""

    def test_paint_with_ghost_cursor(self):
        renderer = OverlayRenderer()
        ctrl = GhostCursorController(duration_ms=50.0)
        ctrl.start_motion(10.0, 10.0, 100.0, 100.0, action_type="click", tooltip="Test")
        renderer.set_ghost_cursor(ctrl)

        mock_painter = MagicMock()
        rect = QRect(0, 0, 300, 300)

        renderer.paint(mock_painter, rect)

        # Should render without exceptions and call painter methods
        assert renderer._ghost_cursor is ctrl
        assert mock_painter.drawEllipse.called
