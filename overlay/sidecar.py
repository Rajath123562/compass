"""
COMPASS Sidecar Chat HUD
Floating glassmorphic chat panel that snaps beside the active application window.
Displays streaming Gemini 3.8 Flash responses, collapsible thinking blocks,
Computer Use intent guidance, and quick approval controls.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

if "QT_QPA_PLATFORM" not in os.environ and ("pytest" in sys.modules or os.environ.get("COMPASS_TEST_MODE")):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide6.QtCore import QPoint, QRect, Qt, Signal
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


# ─── Pure Window Snapping Geometry ─────────────────────────────────────────────

def calculate_snap_position(
    target_rect: tuple[int, int, int, int],
    screen_rect: tuple[int, int, int, int],
    sidecar_w: int = 380,
    sidecar_h: int = 600,
    gap: int = 10,
) -> tuple[int, int]:
    """
    Calculate snap coordinates (x, y) beside a target window.
    
    target_rect: (left, top, right, bottom)
    screen_rect: (screen_x, screen_y, screen_w, screen_h)
    
    Prefers snapping to the right side of target.
    If right side overflows screen, snaps to the left side.
    Clamps bounds so sidecar always remains fully visible inside screen_rect.
    """
    t_left, t_top, t_right, t_bottom = target_rect
    s_x, s_y, s_w, s_h = screen_rect

    # Try right side
    desired_x = t_right + gap
    desired_y = t_top

    # Check right overflow
    if desired_x + sidecar_w > s_x + s_w:
        # Snap to left side
        desired_x = t_left - sidecar_w - gap

    # Check left overflow (if still out-of-bounds, clamp within screen)
    if desired_x < s_x:
        desired_x = s_x + s_w - sidecar_w - gap
    if desired_x < s_x:
        desired_x = s_x

    # Clamp vertical position within screen bounds
    if desired_y + sidecar_h > s_y + s_h:
        desired_y = s_y + s_h - sidecar_h - gap
    if desired_y < s_y:
        desired_y = s_y + gap

    return int(desired_x), int(desired_y)


# ─── Chat Message State Model ──────────────────────────────────────────────────

@dataclass
class SidecarMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: str = "assistant"  # "user" | "assistant" | "system"
    text: str = ""
    thinking: str = ""
    is_streaming: bool = False
    timestamp: float = field(default_factory=time.time)
    action_request: dict[str, Any] | None = None


class SidecarMessageManager:
    """Headless state manager for sidecar messages and streaming tokens."""

    def __init__(self) -> None:
        self.messages: list[SidecarMessage] = []
        self._active_message_id: str | None = None

    def add_user_message(self, text: str) -> SidecarMessage:
        msg = SidecarMessage(sender="user", text=text, is_streaming=False)
        self.messages.append(msg)
        return msg

    def start_assistant_message(self) -> SidecarMessage:
        msg = SidecarMessage(sender="assistant", text="", thinking="", is_streaming=True)
        self.messages.append(msg)
        self._active_message_id = msg.id
        return msg

    def append_thinking(self, message_id: str, chunk: str) -> None:
        msg = self.get_message(message_id)
        if msg:
            msg.thinking += chunk

    def append_text(self, message_id: str, chunk: str) -> None:
        msg = self.get_message(message_id)
        if msg:
            msg.text += chunk

    def finish_message(self, message_id: str) -> None:
        msg = self.get_message(message_id)
        if msg:
            msg.is_streaming = False
        if self._active_message_id == message_id:
            self._active_message_id = None

    def get_message(self, message_id: str) -> SidecarMessage | None:
        for m in self.messages:
            if m.id == message_id:
                return m
        return None

    def clear(self) -> None:
        self.messages.clear()
        self._active_message_id = None


# ─── Glassmorphic PySide6 Sidecar Window ───────────────────────────────────────

if PYSIDE6_AVAILABLE:
    class SidecarHUDWindow(QWidget):
        """
        PySide6 floating glassmorphic chat HUD.
        Stays on top without stealing application focus.
        """

        message_submitted = Signal(str)
        action_decided = Signal(str, dict)  # decision, action_data
        voice_toggled = Signal()

        def __init__(
            self,
            width: int = 380,
            height: int = 600,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._manager = SidecarMessageManager()
            self._drag_pos = QPoint()
            self._pending_action: dict[str, Any] | None = None

            self.resize(width, height)
            self._init_window_flags()
            self._build_ui()
            self._apply_glassmorphic_stylesheet()

        def _init_window_flags(self) -> None:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        def _build_ui(self) -> None:
            # Main container card
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(12, 12, 12, 12)

            self.card_frame = QFrame(self)
            self.card_frame.setObjectName("CardFrame")
            card_layout = QVBoxLayout(self.card_frame)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(10)

            # 1. Header Bar (Drag Bar)
            header_layout = QHBoxLayout()
            header_layout.setSpacing(8)

            self.title_label = QLabel("COMPASS HUD", self.card_frame)
            self.title_label.setObjectName("TitleLabel")

            self.badge_label = QLabel("⚡ Gemini 3.8 Flash", self.card_frame)
            self.badge_label.setObjectName("BadgeLabel")

            header_layout.addWidget(self.title_label)
            header_layout.addWidget(self.badge_label)
            header_layout.addStretch()

            self.close_btn = QPushButton("✕", self.card_frame)
            self.close_btn.setObjectName("HeaderCloseBtn")
            self.close_btn.setFixedSize(22, 22)
            self.close_btn.clicked.connect(self.hide)
            header_layout.addWidget(self.close_btn)

            card_layout.addLayout(header_layout)

            # 2. Messages Scroll Area
            self.scroll_area = QScrollArea(self.card_frame)
            self.scroll_area.setObjectName("ChatScrollArea")
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            self.messages_container = QWidget()
            self.messages_container.setObjectName("MessagesContainer")
            self.messages_layout = QVBoxLayout(self.messages_container)
            self.messages_layout.setContentsMargins(4, 4, 4, 4)
            self.messages_layout.setSpacing(10)
            self.messages_layout.addStretch()

            self.scroll_area.setWidget(self.messages_container)
            card_layout.addWidget(self.scroll_area, stretch=1)

            # 3. Action Confirmation Box (Hidden by default)
            self.action_box = QFrame(self.card_frame)
            self.action_box.setObjectName("ActionBox")
            self.action_box.setVisible(False)
            action_vlayout = QVBoxLayout(self.action_box)
            action_vlayout.setContentsMargins(10, 8, 10, 8)
            action_vlayout.setSpacing(6)

            self.action_title = QLabel("⚠️ Action Requires Confirmation", self.action_box)
            self.action_title.setObjectName("ActionTitle")
            self.action_desc = QLabel("", self.action_box)
            self.action_desc.setObjectName("ActionDesc")
            self.action_desc.setWordWrap(True)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)

            self.btn_approve = QPushButton("✅ Approve", self.action_box)
            self.btn_approve.setObjectName("BtnApprove")
            self.btn_approve.clicked.connect(lambda: self._handle_action_decision("approve"))

            self.btn_skip = QPushButton("⏭️ Skip", self.action_box)
            self.btn_skip.setObjectName("BtnSkip")
            self.btn_skip.clicked.connect(lambda: self._handle_action_decision("skip"))

            self.btn_stop = QPushButton("🛑 Stop", self.action_box)
            self.btn_stop.setObjectName("BtnStop")
            self.btn_stop.clicked.connect(lambda: self._handle_action_decision("stop"))

            btn_row.addWidget(self.btn_approve)
            btn_row.addWidget(self.btn_skip)
            btn_row.addWidget(self.btn_stop)

            action_vlayout.addWidget(self.action_title)
            action_vlayout.addWidget(self.action_desc)
            action_vlayout.addLayout(btn_row)

            card_layout.addWidget(self.action_box)

            # 4. Input Controls Bar
            input_layout = QHBoxLayout()
            input_layout.setSpacing(6)

            self.text_input = QLineEdit(self.card_frame)
            self.text_input.setObjectName("TextInput")
            self.text_input.setPlaceholderText("Ask COMPASS or issue a command...")
            self.text_input.returnPressed.connect(self._handle_send)

            self.mic_btn = QPushButton("🎙️", self.card_frame)
            self.mic_btn.setObjectName("MicButton")
            self.mic_btn.setToolTip("Toggle Voice Input")
            self.mic_btn.setFixedSize(32, 32)
            self.mic_btn.clicked.connect(self.voice_toggled.emit)

            self.send_btn = QPushButton("Send", self.card_frame)
            self.send_btn.setObjectName("SendButton")
            self.send_btn.setFixedSize(54, 32)
            self.send_btn.clicked.connect(self._handle_send)

            input_layout.addWidget(self.text_input, stretch=1)
            input_layout.addWidget(self.mic_btn)
            input_layout.addWidget(self.send_btn)

            card_layout.addLayout(input_layout)
            self.main_layout.addWidget(self.card_frame)

        def _apply_glassmorphic_stylesheet(self) -> None:
            self.setStyleSheet(
                """
                #CardFrame {
                    background-color: rgba(15, 23, 42, 0.94);
                    border: 1px solid rgba(56, 189, 248, 0.35);
                    border-radius: 14px;
                }
                #TitleLabel {
                    color: #38bdf8;
                    font-size: 13px;
                    font-weight: bold;
                    letter-spacing: 0.5px;
                }
                #BadgeLabel {
                    background-color: rgba(56, 189, 248, 0.15);
                    color: #7dd3fc;
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: 600;
                }
                #HeaderCloseBtn {
                    background-color: transparent;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                }
                #HeaderCloseBtn:hover {
                    background-color: rgba(239, 68, 68, 0.3);
                    color: #fca5a5;
                }
                #ChatScrollArea {
                    background-color: transparent;
                    border: none;
                }
                #MessagesContainer {
                    background-color: transparent;
                }
                #ActionBox {
                    background-color: rgba(30, 41, 59, 0.85);
                    border: 1px solid rgba(245, 158, 11, 0.4);
                    border-radius: 8px;
                }
                #ActionTitle {
                    color: #fbbf24;
                    font-size: 11px;
                    font-weight: bold;
                }
                #ActionDesc {
                    color: #e2e8f0;
                    font-size: 11px;
                }
                #BtnApprove {
                    background-color: rgba(16, 185, 129, 0.25);
                    color: #6ee7b7;
                    border: 1px solid rgba(16, 185, 129, 0.5);
                    border-radius: 5px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                #BtnApprove:hover {
                    background-color: rgba(16, 185, 129, 0.45);
                }
                #BtnSkip {
                    background-color: rgba(245, 158, 11, 0.25);
                    color: #fcd34d;
                    border: 1px solid rgba(245, 158, 11, 0.5);
                    border-radius: 5px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                #BtnSkip:hover {
                    background-color: rgba(245, 158, 11, 0.45);
                }
                #BtnStop {
                    background-color: rgba(239, 68, 68, 0.25);
                    color: #fca5a5;
                    border: 1px solid rgba(239, 68, 68, 0.5);
                    border-radius: 5px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                #BtnStop:hover {
                    background-color: rgba(239, 68, 68, 0.45);
                }
                #TextInput {
                    background-color: rgba(30, 41, 59, 0.9);
                    color: #f8fafc;
                    border: 1px solid rgba(56, 189, 248, 0.25);
                    border-radius: 7px;
                    padding: 6px 10px;
                    font-size: 12px;
                }
                #TextInput:focus {
                    border: 1px solid #38bdf8;
                }
                #MicButton {
                    background-color: rgba(30, 41, 59, 0.9);
                    border: 1px solid rgba(56, 189, 248, 0.25);
                    border-radius: 7px;
                    font-size: 13px;
                }
                #MicButton:hover {
                    background-color: rgba(56, 189, 248, 0.2);
                    border-color: #38bdf8;
                }
                #SendButton {
                    background-color: rgba(56, 189, 248, 0.3);
                    color: #38bdf8;
                    border: 1px solid rgba(56, 189, 248, 0.5);
                    border-radius: 7px;
                    font-size: 12px;
                    font-weight: bold;
                }
                #SendButton:hover {
                    background-color: rgba(56, 189, 248, 0.5);
                    color: #ffffff;
                }
                """
            )

        # ── Window Dragging ───────────────────────────────────────────────────────
        def mousePressEvent(self, event) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

        def mouseMoveEvent(self, event) -> None:  # noqa: N802
            if event.buttons() == Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                event.accept()

        # ── Snapping Logic ────────────────────────────────────────────────────────
        def snap_to_target_rect(
            self,
            target_rect: tuple[int, int, int, int],
            screen_rect: tuple[int, int, int, int] | None = None,
        ) -> None:
            """Move sidecar to calculated snap coordinates beside target_rect."""
            if screen_rect is None:
                screens = QGuiApplication.screens()
                if screens:
                    geom = screens[0].availableGeometry()
                    screen_rect = (geom.x(), geom.y(), geom.width(), geom.height())
                else:
                    screen_rect = (0, 0, 1920, 1080)

            x, y = calculate_snap_position(
                target_rect,
                screen_rect,
                sidecar_w=self.width(),
                sidecar_h=self.height(),
            )
            self.move(x, y)

        def snap_to_window(self, hwnd: int | None = None) -> bool:
            """Snap sidecar to the active target Win32 application window."""
            try:
                import ctypes
                from ctypes import wintypes

                if hwnd is None:
                    hwnd = ctypes.windll.user32.GetForegroundWindow()

                if not hwnd:
                    return False

                rect = wintypes.RECT()
                if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    t_rect = (rect.left, rect.top, rect.right, rect.bottom)
                    self.snap_to_target_rect(t_rect)
                    return True
            except Exception:
                pass
            return False

        # ── Message Handling ──────────────────────────────────────────────────────
        def _handle_send(self) -> None:
            text = self.text_input.text().strip()
            if not text:
                return
            self.text_input.clear()
            self.append_user_message(text)
            self.message_submitted.emit(text)

        def append_user_message(self, text: str) -> None:
            self._manager.add_user_message(text)
            bubble = QLabel(text, self.messages_container)
            bubble.setWordWrap(True)
            bubble.setStyleSheet(
                """
                background-color: rgba(30, 41, 59, 0.9);
                color: #f1f5f9;
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                """
            )
            # Insert before stretch
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
            self._scroll_to_bottom()

        def start_assistant_message(self) -> str:
            msg = self._manager.start_assistant_message()
            container = QFrame(self.messages_container)
            container.setObjectName(f"msg_{msg.id}")
            c_layout = QVBoxLayout(container)
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.setSpacing(4)

            # Thinking block
            thinking_label = QLabel(container)
            thinking_label.setObjectName("ThinkingBlock")
            thinking_label.setVisible(False)
            thinking_label.setWordWrap(True)
            thinking_label.setStyleSheet(
                """
                background-color: rgba(15, 23, 42, 0.6);
                color: #94a3b8;
                border-left: 2px solid #38bdf8;
                padding: 4px 8px;
                font-size: 11px;
                font-style: italic;
                """
            )

            # Main text bubble
            bubble = QLabel(container)
            bubble.setObjectName("AssistantText")
            bubble.setWordWrap(True)
            bubble.setStyleSheet(
                """
                background-color: rgba(56, 189, 248, 0.12);
                color: #f8fafc;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                """
            )

            c_layout.addWidget(thinking_label)
            c_layout.addWidget(bubble)

            self.messages_layout.insertWidget(self.messages_layout.count() - 1, container)
            self._scroll_to_bottom()
            return msg.id

        def append_assistant_chunk(self, msg_id: str, text_chunk: str, thinking_chunk: str = "") -> None:
            self._manager.append_text(msg_id, text_chunk)
            if thinking_chunk:
                self._manager.append_thinking(msg_id, thinking_chunk)

            msg = self._manager.get_message(msg_id)
            if not msg:
                return

            container = self.messages_container.findChild(QFrame, f"msg_{msg_id}")
            if container:
                t_label = container.findChild(QLabel, "ThinkingBlock")
                b_label = container.findChild(QLabel, "AssistantText")

                if t_label and msg.thinking:
                    t_label.setText(f"💭 Thinking:\n{msg.thinking}")
                    t_label.setVisible(True)

                if b_label:
                    b_label.setText(msg.text)

            self._scroll_to_bottom()

        def finish_assistant_message(self, msg_id: str) -> None:
            self._manager.finish_message(msg_id)

        def set_pending_action(self, action_data: dict[str, Any]) -> None:
            self._pending_action = action_data
            action_type = action_data.get("action_type", "action")
            target = action_data.get("target", "system")
            reason = action_data.get("reason", "Action requires human approval")
            self.action_desc.setText(f"Type: {action_type}\nTarget: {target}\nReason: {reason}")
            self.action_box.setVisible(True)
            self._scroll_to_bottom()

        def _handle_action_decision(self, decision: str) -> None:
            self.action_box.setVisible(False)
            action = self._pending_action or {}
            self._pending_action = None
            self.action_decided.emit(decision, action)

        def _scroll_to_bottom(self) -> None:
            sb = self.scroll_area.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
