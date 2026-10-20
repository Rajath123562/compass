"""
COMPASS Transparent PySide6 Overlay Window
Phase 2: Extended with OverlayRenderer for UI element bounding box visualization.

Properties maintained from Phase 1:
  - Frameless, always-on-top, tool window
  - WA_TranslucentBackground
  - DPI-aware
  - Click-through (WS_EX_TRANSPARENT)
  - Escape to close
  - Non-invasive: never steals focus from target application
"""

from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from overlay.renderer import OverlayRenderer
from overlay.win32_helper import make_window_click_through


class CompassOverlayWindow(QWidget):
    def __init__(
        self,
        click_through: bool = False,
        auto_close_sec: float = 0.0,
        poll_interval_ms: int = 500,
    ):
        super().__init__()
        self.click_through_enabled = click_through
        self.auto_close_sec = auto_close_sec
        self._renderer = OverlayRenderer()
        self._phase2_active = False  # True when element visualization is running

        # Configure frameless, always-on-top, tool window properties
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Enable full background translucency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Ensure application quits when this window is closed
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, True)

        # Geometry: cover virtual desktop spanning all connected screens (multi-monitor support)
        screens = QApplication.screens()
        if screens:
            virtual_rect = QRect()
            for s in screens:
                virtual_rect = virtual_rect.united(s.geometry())
            self.setGeometry(virtual_rect)
        else:
            self.setGeometry(0, 0, 1920, 1080)

        # Auto-close timer if specified
        if self.auto_close_sec > 0:
            QTimer.singleShot(int(self.auto_close_sec * 1000), self._auto_close)

    def _auto_close(self):
        self.close()
        app = QApplication.instance()
        if app:
            app.quit()

    def closeEvent(self, event):
        super().closeEvent(event)
        app = QApplication.instance()
        if app:
            app.quit()

    def showEvent(self, event):
        super().showEvent(event)
        # Apply native click-through extended window style once window handle (HWND) is valid
        if self.click_through_enabled:
            hwnd = int(self.winId())
            make_window_click_through(hwnd, enable=True)

    def set_click_through(self, enable: bool):
        self.click_through_enabled = enable
        hwnd = int(self.winId())
        return make_window_click_through(hwnd, enable=enable)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    # ── Phase 2: Element visualization API ────────────────────────────────────

    def update_elements(self, elements: list[dict[str, Any]]) -> None:
        """
        Update the bounding box annotations.
        Call this from a background thread (uses update() to trigger repaint safely).
        """
        self._renderer.set_elements(elements)
        self._phase2_active = True
        self.update()  # Trigger Qt repaint on main thread

    def highlight_element(self, element_id: str | None) -> None:
        """Highlight a specific element by its element_id."""
        self._renderer.highlight(element_id)
        self.update()

    def clear_annotations(self) -> None:
        """Remove all bounding box annotations."""
        self._renderer.clear()
        self._phase2_active = False
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Phase 2: Render element bounding boxes if active
        if self._phase2_active and self._renderer.element_count > 0:
            self._renderer.paint(painter, self.rect())
        else:
            # Phase 1 / idle: Minimal diagnostic HUD at top center
            self._paint_idle_hud(painter)

        painter.end()

    def _paint_idle_hud(self, painter: QPainter) -> None:
        """Phase 1 diagnostic HUD — shown when no elements are being visualized."""
        badge_w = 480
        badge_h = 42
        x = (self.width() - badge_w) // 2
        y = 20

        badge_rect = QRect(x, y, badge_w, badge_h)
        bg_color = QColor(15, 23, 42, 220)
        border_color = QColor(56, 189, 248, 180)
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(badge_rect, 10, 10)

        dot_color = QColor(34, 197, 94, 255)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dot_color))
        painter.drawEllipse(x + 18, y + 14, 12, 12)

        painter.setPen(QColor(241, 245, 249))
        font = QFont("Segoe UI", 10, QFont.Weight.Medium)
        painter.setFont(font)
        text = "COMPASS Guidance Overlay (Phase 2 Ready) — [Esc to close]"
        painter.drawText(
            badge_rect.adjusted(38, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text
        )
