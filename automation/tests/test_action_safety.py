"""
Tests for automation/safety.py — safety guard edge cases
"""

import sys
from unittest.mock import patch

import pytest

from automation import safety
from automation.models import PROTECTED_WINDOW_CLASSES


class TestProtectedWindowClasses:
    def test_protected_list_not_empty(self):
        assert len(PROTECTED_WINDOW_CLASSES) > 0

    def test_taskbar_is_protected(self):
        assert "Shell_TrayWnd" in PROTECTED_WINDOW_CLASSES

    def test_desktop_is_protected(self):
        assert "Progman" in PROTECTED_WINDOW_CLASSES


class TestHWNDSafe:
    @patch("automation.safety._is_window", return_value=True)
    @patch("automation.safety._get_window_class", return_value="Notepad")
    def test_regular_window_safe(self, mock_cls, mock_win):
        result = safety.check_hwnd_safe(12345)
        assert result.ok is True

    @patch("automation.safety._is_window", return_value=True)
    @patch("automation.safety._get_window_class", return_value="Shell_TrayWnd")
    def test_taskbar_hwnd_rejected(self, mock_cls, mock_win):
        result = safety.check_hwnd_safe(12345)
        assert result.ok is False
        assert "protected" in result.reason.lower()

    @patch("automation.safety._is_window", return_value=False)
    def test_invalid_hwnd_rejected(self, mock_win):
        result = safety.check_hwnd_safe(999999999)
        assert result.ok is False

    def test_zero_hwnd_rejected(self):
        result = safety.check_hwnd_safe(0)
        assert result.ok is False


class TestForegroundContext:
    def test_non_windows_returns_error(self):
        if sys.platform == "win32":
            pytest.skip("Non-Windows test only")
        result = safety.check_foreground_context(12345)
        assert result.ok is False

    @patch(
        "automation.safety.ctypes.windll.user32.GetForegroundWindow", return_value=12345
    )
    @patch("automation.safety.ctypes.windll.user32.GetAncestor", return_value=12345)
    def test_matching_hwnd_passes(self, mock_ancestor, mock_fg):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = safety.check_foreground_context(12345)
        assert result.ok is True


class TestActionSafetyModels:
    def test_max_type_length_defined(self):
        from automation.models import MAX_TYPE_LENGTH

        assert MAX_TYPE_LENGTH > 0
        assert MAX_TYPE_LENGTH <= 100000

    def test_protected_windows_classes_are_strings(self):
        for cls in PROTECTED_WINDOW_CLASSES:
            assert isinstance(cls, str)
            assert len(cls) > 0
