"""
COMPASS Ghost Cursor and Neon Visual Guidance Engine
Computes smooth Bezier motion curves, neon spotlight pulse effects,
and step guidance indicators for the transparent overlay.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

# Neon color definitions
NEON_CYAN = (0, 240, 255)       # Click / default
NEON_EMERALD = (16, 185, 129)   # Type
NEON_AMBER = (245, 158, 11)     # Scroll
NEON_ROSE = (244, 63, 94)       # Danger / confirmation
NEON_PURPLE = (168, 85, 247)    # Trail gradient


@dataclass
class Point2D:
    x: float
    y: float


@dataclass
class CursorTrailPoint:
    x: float
    y: float
    alpha: float
    radius: float
    timestamp: float


@dataclass
class GhostCursorState:
    """Current state of the animated ghost cursor."""
    current_x: float
    current_y: float
    target_x: float
    target_y: float
    action_type: str = "click"
    progress: float = 1.0  # 0.0 to 1.0
    is_animating: bool = False
    pulse_radius: float = 0.0
    pulse_alpha: float = 0.0
    tooltip_text: str = ""
    step_label: str = ""
    trail: list[CursorTrailPoint] = field(default_factory=list)


def cubic_bezier_point(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D, t: float) -> Point2D:
    """Compute (x, y) on a cubic Bezier curve at parameter t in [0, 1]."""
    u = 1.0 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * p0.x + 3 * uu * t * p1.x + 3 * u * tt * p2.x + ttt * p3.x
    y = uuu * p0.y + 3 * uu * t * p1.y + 3 * u * tt * p2.y + ttt * p3.y
    return Point2D(x=x, y=y)


def ease_in_out_cubic(t: float) -> float:
    """Smooth easing function for natural hand-like cursor motion."""
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        f = 2.0 * t - 2.0
        return 0.5 * f * f * f + 1.0


class GhostCursorController:
    """Calculates coordinates, trails, and pulses for the overlay renderer."""

    def __init__(self, duration_ms: float = 600.0) -> None:
        self.duration_ms = duration_ms
        self.state = GhostCursorState(
            current_x=0.0,
            current_y=0.0,
            target_x=0.0,
            target_y=0.0,
        )
        self._start_pos = Point2D(0.0, 0.0)
        self._target_pos = Point2D(0.0, 0.0)
        self._ctrl_1 = Point2D(0.0, 0.0)
        self._ctrl_2 = Point2D(0.0, 0.0)
        self._animation_start_time: float = 0.0

    def start_motion(
        self,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        action_type: str = "click",
        tooltip: str = "",
        step_label: str = "",
    ) -> None:
        """Initialize a new curved Bezier trajectory towards (to_x, to_y)."""
        self._start_pos = Point2D(from_x, from_y)
        self._target_pos = Point2D(to_x, to_y)

        # Generate natural arc control points
        dx = to_x - from_x
        dy = to_y - from_y
        dist = math.hypot(dx, dy)
        # Perpendicular normal offset for subtle natural curve
        arc_offset = min(80.0, dist * 0.2)

        self._ctrl_1 = Point2D(from_x + dx * 0.25 - dy * 0.05, from_y + dy * 0.25 + arc_offset)
        self._ctrl_2 = Point2D(from_x + dx * 0.75 + dy * 0.05, from_y + dy * 0.75 - arc_offset * 0.5)

        self.state.target_x = to_x
        self.state.target_y = to_y
        self.state.action_type = action_type
        self.state.tooltip_text = tooltip
        self.state.step_label = step_label
        self.state.progress = 0.0
        self.state.is_animating = True
        self.state.trail.clear()
        self._animation_start_time = time.time()

    def update(self) -> GhostCursorState:
        """Step the animation state forward by current time delta."""
        if not self.state.is_animating:
            # Subtle idle pulse at target
            now = time.time()
            pulse_phase = (now * 2.5) % (2.0 * math.pi)
            self.state.pulse_radius = 24.0 + 8.0 * math.sin(pulse_phase)
            self.state.pulse_alpha = 0.4 + 0.3 * math.sin(pulse_phase)
            return self.state

        elapsed_ms = (time.time() - self._animation_start_time) * 1000.0
        raw_t = min(1.0, elapsed_ms / self.duration_ms) if self.duration_ms > 0 else 1.0
        eased_t = ease_in_out_cubic(raw_t)

        pt = cubic_bezier_point(
            self._start_pos, self._ctrl_1, self._ctrl_2, self._target_pos, eased_t
        )
        self.state.current_x = pt.x
        self.state.current_y = pt.y
        self.state.progress = raw_t

        # Add to motion trail
        self.state.trail.append(
            CursorTrailPoint(
                x=pt.x,
                y=pt.y,
                alpha=0.8,
                radius=6.0,
                timestamp=time.time(),
            )
        )

        # Decay old trail points
        now = time.time()
        self.state.trail = [
            CursorTrailPoint(
                x=p.x,
                y=p.y,
                alpha=max(0.0, p.alpha - 0.08),
                radius=max(1.0, p.radius * 0.95),
                timestamp=p.timestamp,
            )
            for p in self.state.trail
            if (now - p.timestamp) < 0.35 and p.alpha > 0.05
        ]

        if raw_t >= 1.0:
            self.state.is_animating = False
            self.state.current_x = self.state.target_x
            self.state.current_y = self.state.target_y

        return self.state

    def get_action_color(self) -> tuple[int, int, int]:
        """Return RGB tuple matching current action type."""
        atype = self.state.action_type.lower()
        if atype in ("type", "write"):
            return NEON_EMERALD
        elif atype == "scroll":
            return NEON_AMBER
        elif atype in ("danger", "confirm", "require_confirmation"):
            return NEON_ROSE
        return NEON_CYAN
