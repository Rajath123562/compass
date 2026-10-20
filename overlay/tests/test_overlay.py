"""
Unit and integration tests for the COMPASS PySide6 Overlay Foundation.
"""

import subprocess
import sys
import pytest

from overlay.win32_helper import set_dpi_awareness

pyside6_available = False
try:
    _res = subprocess.run([sys.executable, "-c", "import PySide6"], capture_output=True, timeout=5)
    pyside6_available = (_res.returncode == 0)
except Exception:
    pyside6_available = False


def test_dpi_awareness():
    res = set_dpi_awareness()
    assert isinstance(res, bool)


@pytest.mark.skipif(not pyside6_available, reason="PySide6 not installed")
def test_overlay_window_properties():
    # Run in isolated subprocess to prevent Qt/COM C++ destructor conflict on process teardown
    cmd = [
        sys.executable,
        "-c",
        """
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from overlay.win32_helper import make_window_click_through
from overlay.window import CompassOverlayWindow

app = QApplication.instance() or QApplication([])
window = CompassOverlayWindow(click_through=False, auto_close_sec=0)

flags = window.windowFlags()
assert bool(flags & Qt.WindowType.FramelessWindowHint) is True
assert bool(flags & Qt.WindowType.WindowStaysOnTopHint) is True
assert bool(flags & Qt.WindowType.Tool) is True
assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is True

window.show()
hwnd = int(window.winId())
assert hwnd > 0

success = make_window_click_through(hwnd, enable=True)
assert isinstance(success, bool)
window.close()
print('PROPERTIES_OK')
""",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: PLW1510
    assert proc.returncode == 0
    assert "PROPERTIES_OK" in proc.stdout


@pytest.mark.skipif(not pyside6_available, reason="PySide6 not installed")
def test_overlay_subprocess_clean_exit():
    cmd = [sys.executable, "-m", "overlay.launcher", "--duration", "1.0"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: PLW1510
    assert proc.returncode == 0
    assert "Closed cleanly" in proc.stdout
