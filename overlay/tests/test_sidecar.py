"""
Unit and integration tests for COMPASS Sidecar Chat HUD (Phase 5).
"""

import subprocess
import sys
import pytest

from overlay.sidecar import (
    SidecarMessageManager,
    calculate_snap_position,
)

pyside6_available = False
try:
    _res = subprocess.run([sys.executable, "-c", "import PySide6"], capture_output=True, timeout=5)
    pyside6_available = (_res.returncode == 0)
except Exception:
    pyside6_available = False


class TestSidecarSnappingGeometry:
    """Test pure geometry calculations for sidecar snapping."""

    def test_snap_to_right_side(self):
        # Target at left=100, top=100, right=600, bottom=500
        # Screen at 0, 0, 1920, 1080
        # Sidecar 380x600, gap 10
        x, y = calculate_snap_position(
            target_rect=(100, 100, 600, 500),
            screen_rect=(0, 0, 1920, 1080),
            sidecar_w=380,
            sidecar_h=600,
            gap=10,
        )
        assert x == 610  # 600 + 10
        assert y == 100

    def test_snap_to_left_side_when_right_overflows(self):
        # Target at right=1800, right+10+380 = 2190 > 1920
        # Target left=1000
        x, y = calculate_snap_position(
            target_rect=(1000, 100, 1800, 500),
            screen_rect=(0, 0, 1920, 1080),
            sidecar_w=380,
            sidecar_h=600,
            gap=10,
        )
        assert x == 610  # 1000 - 380 - 10
        assert y == 100

    def test_snap_vertical_clamping(self):
        # Target near bottom: top=800, bottom=1000
        # sidecar_h=600 -> 800+600 = 1400 > 1080
        x, y = calculate_snap_position(
            target_rect=(100, 800, 500, 1000),
            screen_rect=(0, 0, 1920, 1080),
            sidecar_w=380,
            sidecar_h=600,
            gap=10,
        )
        # Should be clamped so bottom edge is within screen
        assert y + 600 <= 1080


class TestSidecarMessageManager:
    """Test headless message state management and streaming."""

    def test_user_message_lifecycle(self):
        mgr = SidecarMessageManager()
        msg = mgr.add_user_message("Hello COMPASS")
        assert len(mgr.messages) == 1
        assert msg.sender == "user"
        assert msg.text == "Hello COMPASS"
        assert msg.is_streaming is False

    def test_assistant_streaming_message(self):
        mgr = SidecarMessageManager()
        msg = mgr.start_assistant_message()
        assert msg.sender == "assistant"
        assert msg.is_streaming is True
        assert mgr._active_message_id == msg.id

        # Stream thinking
        mgr.append_thinking(msg.id, "Analyzing screen context... ")
        mgr.append_thinking(msg.id, "Found target element.")
        assert msg.thinking == "Analyzing screen context... Found target element."

        # Stream content text
        mgr.append_text(msg.id, "Clicking the ")
        mgr.append_text(msg.id, "Submit button.")
        assert msg.text == "Clicking the Submit button."

        # Finish message
        mgr.finish_message(msg.id)
        assert msg.is_streaming is False
        assert mgr._active_message_id is None

    def test_clear_messages(self):
        mgr = SidecarMessageManager()
        mgr.add_user_message("Test")
        mgr.clear()
        assert len(mgr.messages) == 0


@pytest.mark.skipif(not pyside6_available, reason="PySide6 not installed")
def test_sidecar_window_lifecycle_and_actions():
    """Verify PySide6 Sidecar window, controls, and action signaling in isolated process."""
    cmd = [
        sys.executable,
        "-c",
        """
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from overlay.sidecar import SidecarHUDWindow

app = QApplication.instance() or QApplication([])
win = SidecarHUDWindow(width=380, height=600)

flags = win.windowFlags()
assert bool(flags & Qt.WindowType.FramelessWindowHint) is True
assert bool(flags & Qt.WindowType.WindowStaysOnTopHint) is True
assert bool(flags & Qt.WindowType.Tool) is True

# Test sending user message
win.append_user_message("User prompt test")

# Test assistant streaming
msg_id = win.start_assistant_message()
win.append_assistant_chunk(msg_id, "Result text", thinking_chunk="Reasoning step")
win.finish_assistant_message(msg_id)

win.show()

# Test pending action box
received_decisions = []
win.action_decided.connect(lambda dec, data: received_decisions.append((dec, data)))

test_action = {"action_type": "click", "target": "SubmitBtn", "reason": "High risk"}
win.set_pending_action(test_action)
assert not win.action_box.isHidden()

# Click Approve
win.btn_approve.click()
assert win.action_box.isHidden()
assert len(received_decisions) == 1
assert received_decisions[0][0] == "approve"
assert received_decisions[0][1]["action_type"] == "click"

# Test snap to rect
win.snap_to_target_rect((100, 100, 400, 500), screen_rect=(0, 0, 1920, 1080))
assert win.x() == 410
assert win.y() == 100

win.close()
print("SIDECAR_TESTS_OK")
""",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
    assert proc.returncode == 0, f"Error: {proc.stderr}"
    assert "SIDECAR_TESTS_OK" in proc.stdout
