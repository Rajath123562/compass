"""
COMPASS Overlay Renderer
Draws bounding box annotations and labels for discovered UI elements
on the transparent overlay window.

Designed as a diagnostic visualization tool for Phase 2.
Does NOT claim to represent intelligent guidance — it visualizes
what UIA has discovered.

Properties:
  - DPI-aware coordinate mapping
  - Color-coded by control type
  - Labels with element name + control type
  - Selected/highlighted element support
  - Clear all annotations
  - Never steals focus from target application
"""

import os
import sys
from typing import Any

if "QT_QPA_PLATFORM" not in os.environ and ("pytest" in sys.modules or os.environ.get("COMPASS_TEST_MODE")):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen

# ─── Color palette by control type ────────────────────────────────────────────
CONTROL_TYPE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "Button": (56, 189, 248, 200),  # Sky-400
    "Edit": (52, 211, 153, 200),  # Emerald-400
    "Document": (52, 211, 153, 200),  # Emerald-400
    "CheckBox": (251, 191, 36, 200),  # Amber-400
    "ComboBox": (251, 191, 36, 200),  # Amber-400
    "MenuItem": (167, 139, 250, 200),  # Violet-400
    "MenuBar": (167, 139, 250, 160),  # Violet-400
    "ListItem": (196, 181, 253, 200),  # Violet-300
    "Tab": (129, 140, 248, 200),  # Indigo-400
    "TabItem": (129, 140, 248, 200),  # Indigo-400
    "Text": (148, 163, 184, 180),  # Slate-400
    "TreeItem": (34, 211, 238, 200),  # Cyan-400
    "DataItem": (34, 211, 238, 200),  # Cyan-400
    "Window": (248, 113, 113, 160),  # Red-400
    "Pane": (74, 222, 128, 120),  # Green-400
    "default": (226, 232, 240, 160),  # Slate-200
}

FILL_ALPHA = 20  # Very light fill
BORDER_WIDTH = 1.5
LABEL_FONT_SIZE = 9
HIGHLIGHT_BORDER_WIDTH = 2.5


def _control_color(control_type: str, alpha_override: int = -1) -> QColor:
    rgba = CONTROL_TYPE_COLORS.get(control_type, CONTROL_TYPE_COLORS["default"])
    a = alpha_override if alpha_override >= 0 else rgba[3]
    return QColor(rgba[0], rgba[1], rgba[2], a)


class OverlayRenderer:
    """
    Manages a list of annotated UI elements and renders them onto a QPainter surface.

    Usage:
        renderer = OverlayRenderer()
        renderer.set_elements(element_dicts)
        # Called from QWidget.paintEvent:
        renderer.paint(painter, widget_rect)
    """

    def __init__(self):
        self._elements: list[dict[str, Any]] = []
        self._highlighted_id: str | None = None
        self._visible = True
        self._ghost_spotlight: dict[str, int] | None = None
        self._ghost_tooltip: str = ""
        self._ghost_cursor = None

    def set_ghost_cursor(self, cursor_controller: Any) -> None:
        """Attach or update the GhostCursorController."""
        self._ghost_cursor = cursor_controller

    def set_elements(self, elements: list[dict[str, Any]]) -> None:
        """Update the element list to render. Thread-safe call required from Qt thread."""
        self._elements = list(elements)

    def set_ghost_spotlight(self, rect: dict[str, int] | None, tooltip: str = "") -> None:
        """
        Configure Ghost Guidance spotlight.
        Renders a gentle glowing neon aura and direction tooltip around the target element
        without moving the physical mouse cursor or stealing application focus.
        """
        self._ghost_spotlight = rect
        self._ghost_tooltip = tooltip

    def highlight(self, element_id: str | None) -> None:
        """Highlight a specific element by ID (None to clear highlight)."""
        self._highlighted_id = element_id

    def clear(self) -> None:
        """Remove all annotations."""
        self._elements = []
        self._highlighted_id = None
        self._ghost_spotlight = None
        self._ghost_tooltip = ""
        self._ghost_cursor = None

    def set_visible(self, visible: bool) -> None:
        self._visible = visible

    @property
    def element_count(self) -> int:
        return len(self._elements)

    def paint(self, painter: QPainter, widget_rect: QRect) -> None:
        """
        Render all annotations onto the provided QPainter.
        Called from the overlay window's paintEvent.
        """
        if not self._visible or (
            not self._elements and not self._ghost_spotlight and not self._ghost_cursor
        ):
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._ghost_spotlight:
            self._draw_ghost_spotlight(painter, widget_rect)

        if self._ghost_cursor:
            self._draw_ghost_cursor(painter, widget_rect)

        if self._elements and QGuiApplication.instance() is not None:
            try:
                label_font = QFont("Segoe UI", LABEL_FONT_SIZE)
                painter.setFont(label_font)
                fm = QFontMetrics(label_font)
            except Exception:
                fm = None
        else:
            fm = None

        for el in self._elements:
            bounds = el.get("bounds", {})
            left = bounds.get("left", 0)
            top = bounds.get("top", 0)
            width = bounds.get("width", 0)
            height = bounds.get("height", 0)

            # Skip zero-area elements
            if width <= 0 or height <= 0:
                continue

            ct = el.get("control_type", "")
            name = el.get("name", "")[:40]  # Truncate long names
            el_id = el.get("element_id", "")
            is_highlighted = el_id == self._highlighted_id

            rect = QRect(left, top, width, height)
            border_color = _control_color(ct, 200 if is_highlighted else 160)
            fill_color = _control_color(ct, 35 if is_highlighted else FILL_ALPHA)

            # Draw filled rect
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill_color))
            painter.drawRect(rect)

            # Draw border
            pen_width = HIGHLIGHT_BORDER_WIDTH if is_highlighted else BORDER_WIDTH
            painter.setPen(QPen(border_color, pen_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            # Draw label (top-left of element, clipped to widget)
            if name or ct:
                label = f"{ct}: {name}" if name else ct
                if fm:
                    label_w = fm.horizontalAdvance(label) + 8
                    label_h = fm.height() + 4
                else:
                    label_w = len(label) * 8 + 8
                    label_h = 16

                lx = max(0, left)
                ly = max(0, top - label_h - 2)
                # Ensure label stays inside widget
                if ly < 0:
                    ly = top + 2
                lx = min(lx, widget_rect.width() - label_w)

                label_rect = QRect(lx, ly, label_w, label_h)

                # Label background
                label_bg = QColor(15, 23, 42, 200)  # Dark slate
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(label_bg))
                painter.drawRoundedRect(label_rect, 3, 3)

                # Label text
                painter.setPen(border_color)
                painter.drawText(
                    label_rect.adjusted(4, 2, -4, -2),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    label,
                )

        # Draw element count badge (bottom-right)
        self._draw_count_badge(painter, widget_rect)

    def _draw_count_badge(self, painter: QPainter, widget_rect: QRect) -> None:
        """Draw a small info badge showing how many elements are being visualized."""
        count = len(self._elements)
        if count == 0:
            return

        text = f"COMPASS UIA  ·  {count} elements"
        if QGuiApplication.instance() is not None:
            font = QFont("Segoe UI", 9)
            painter.setFont(font)
            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(text) + 20
            h = fm.height() + 10
        else:
            w = len(text) * 8 + 20
            h = 24
        x = widget_rect.width() - w - 16
        y = widget_rect.height() - h - 16

        badge = QRect(x, y, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
        painter.drawRoundedRect(badge, 6, 6)

        painter.setPen(QColor(56, 189, 248, 220))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_ghost_spotlight(self, painter: QPainter, widget_rect: QRect) -> None:
        """Draw non-intrusive glowing neon halo and guidance card."""
        if not self._ghost_spotlight:
            return

        left = self._ghost_spotlight.get("left", 0)
        top = self._ghost_spotlight.get("top", 0)
        width = self._ghost_spotlight.get("width", 0)
        height = self._ghost_spotlight.get("height", 0)

        if width <= 0 or height <= 0:
            return

        target_rect = QRect(left, top, width, height)

        # 1. Subtle soft halo (expanded outer ring)
        halo_rect = target_rect.adjusted(-6, -6, 6, 6)
        painter.setPen(QPen(QColor(56, 189, 248, 80), 3))
        painter.setBrush(QBrush(QColor(56, 189, 248, 20)))
        painter.drawRoundedRect(halo_rect, 8, 8)

        # 2. Crisp neon inner border
        painter.setPen(QPen(QColor(14, 165, 233, 230), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(target_rect, 4, 4)

        # 3. Floating Guidance Tooltip Card
        if self._ghost_tooltip:
            text = f"✨ {self._ghost_tooltip}"
            if QGuiApplication.instance() is not None:
                font = QFont("Segoe UI", 10)
                painter.setFont(font)
                fm = QFontMetrics(font)
                card_w = fm.horizontalAdvance(text) + 24
                card_h = fm.height() + 12
            else:
                card_w = len(text) * 8 + 24
                card_h = 24

            # Place above target if room, else below
            card_x = max(10, left + (width // 2) - (card_w // 2))
            card_y = top - card_h - 8
            if card_y < 10:
                card_y = top + height + 8
            card_x = min(card_x, widget_rect.width() - card_w - 10)

            card_rect = QRect(card_x, card_y, card_w, card_h)

            # Card background (Dark obsidian glass)
            painter.setPen(QPen(QColor(56, 189, 248, 180), 1))
            painter.setBrush(QBrush(QColor(15, 23, 42, 240)))
            painter.drawRoundedRect(card_rect, 6, 6)

            # Card text
            painter.setPen(QColor(241, 245, 249))
            painter.drawText(
                card_rect,
                Qt.AlignmentFlag.AlignCenter,
                text,
            )

    def _draw_ghost_cursor(self, painter: QPainter, widget_rect: QRect) -> None:
        """Render animated ghost cursor, glowing trail, and pulse ring."""
        if not self._ghost_cursor:
            return

        try:
            state = self._ghost_cursor.update()
            r, g, b = self._ghost_cursor.get_action_color()

            # 1. Draw glowing trail
            for p in state.trail:
                alpha = int(p.alpha * 180)
                if alpha > 0:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(r, g, b, alpha)))
                    painter.drawEllipse(
                        int(p.x - p.radius),
                        int(p.y - p.radius),
                        int(p.radius * 2),
                        int(p.radius * 2),
                    )

            # 2. Draw destination pulse ring
            if state.pulse_radius > 0:
                p_alpha = int(state.pulse_alpha * 200)
                painter.setPen(QPen(QColor(r, g, b, p_alpha), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(
                    int(state.target_x - state.pulse_radius),
                    int(state.target_y - state.pulse_radius),
                    int(state.pulse_radius * 2),
                    int(state.pulse_radius * 2),
                )

            # 3. Draw Ghost Cursor Hand/Pointer
            cx, cy = int(state.current_x), int(state.current_y)
            # Outer neon glow
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(r, g, b, 70)))
            painter.drawEllipse(cx - 14, cy - 14, 28, 28)

            # Inner bright core
            painter.setBrush(QBrush(QColor(r, g, b, 220)))
            painter.drawEllipse(cx - 6, cy - 6, 12, 12)

            # Center white star
            painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
            painter.drawEllipse(cx - 2, cy - 2, 4, 4)

            # 4. Optional floating step tooltip
            if state.tooltip_text or state.step_label:
                disp_text = (
                    f"{state.step_label}: {state.tooltip_text}"
                    if state.step_label
                    else state.tooltip_text
                )
                if QGuiApplication.instance() is not None:
                    try:
                        font = QFont("Segoe UI", 9)
                        painter.setFont(font)
                        fm = QFontMetrics(font)
                        card_w = fm.horizontalAdvance(disp_text) + 20
                        card_h = fm.height() + 10
                    except Exception:
                        card_w = len(disp_text) * 8 + 20
                        card_h = 24
                else:
                    card_w = len(disp_text) * 8 + 20
                    card_h = 24

                card_x = min(max(10, cx + 18), widget_rect.width() - card_w - 10)
                card_y = min(max(10, cy - 10), widget_rect.height() - card_h - 10)

                card_rect = QRect(card_x, card_y, card_w, card_h)
                painter.setPen(QPen(QColor(r, g, b, 180), 1))
                painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
                painter.drawRoundedRect(card_rect, 5, 5)

                painter.setPen(QColor(241, 245, 249))
                painter.drawText(card_rect, Qt.AlignmentFlag.AlignCenter, disp_text)
        except Exception:
            pass

