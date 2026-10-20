"""
Tests for automation/action_validator.py + automation/safety.py
Pure unit tests using deterministic inputs — no actual UI automation fired.
"""

from unittest.mock import patch

from automation import safety
from automation.action_validator import ActionValidator
from automation.models import VK_CODES


class TestKeySafety:
    def test_allowed_key_passes(self):
        result = safety.check_key_safe("enter")
        assert result.ok is True

    def test_all_vk_codes_pass(self):
        for key in VK_CODES:
            result = safety.check_key_safe(key)
            assert result.ok is True, f"Key '{key}' should be allowed"

    def test_unknown_key_rejected(self):
        result = safety.check_key_safe("__notakey__")
        assert result.ok is False
        assert "allowed" in result.reason.lower() or "not in" in result.reason.lower()

    def test_case_insensitive(self):
        result = safety.check_key_safe("ENTER")
        assert result.ok is True

    def test_empty_key_rejected(self):
        result = safety.check_key_safe("")
        assert result.ok is False


class TestTextSafety:
    def test_normal_text_passes(self):
        result = safety.check_text_safe("Hello World")
        assert result.ok is True

    def test_empty_string_passes(self):
        # Empty string is technically valid (length 0 <= MAX_TYPE_LENGTH)
        result = safety.check_text_safe("")
        assert result.ok is True

    def test_oversized_text_rejected(self):
        big = "x" * 10001
        result = safety.check_text_safe(big)
        assert result.ok is False
        assert "maximum" in result.reason.lower() or "length" in result.reason.lower()

    def test_none_rejected(self):
        result = safety.check_text_safe(None)
        assert result.ok is False

    def test_exactly_at_limit_passes(self):
        from automation.models import MAX_TYPE_LENGTH

        text = "a" * MAX_TYPE_LENGTH
        result = safety.check_text_safe(text)
        assert result.ok is True


class TestElementActionable:
    def _make_el(self, **kwargs):
        base = {
            "hwnd": 12345,
            "name": "TestElement",
            "control_type": "Edit",
            "is_enabled": True,
            "is_visible": True,
            "bounds": {
                "left": 0,
                "top": 0,
                "right": 100,
                "bottom": 40,
                "width": 100,
                "height": 40,
            },
            "automation_id": "test_id",
        }
        base.update(kwargs)
        return base

    @patch("automation.safety._is_window", return_value=True)
    def test_valid_element_passes(self, mock_win):
        el = self._make_el()
        result = safety.check_element_actionable(el)
        assert result.ok is True

    @patch("automation.safety._is_window", return_value=True)
    def test_disabled_element_rejected(self, mock_win):
        el = self._make_el(is_enabled=False)
        result = safety.check_element_actionable(el)
        assert result.ok is False
        assert "disabled" in result.reason.lower()

    @patch("automation.safety._is_window", return_value=True)
    def test_invisible_element_rejected(self, mock_win):
        el = self._make_el(is_visible=False)
        result = safety.check_element_actionable(el)
        assert result.ok is False

    @patch("automation.safety._is_window", return_value=True)
    def test_zero_bounds_rejected(self, mock_win):
        el = self._make_el(
            bounds={
                "left": 0,
                "top": 0,
                "right": 0,
                "bottom": 0,
                "width": 0,
                "height": 0,
            }
        )
        result = safety.check_element_actionable(el)
        assert result.ok is False
        assert "zero" in result.reason.lower() or "rect" in result.reason.lower()

    @patch("automation.safety._is_window", return_value=False)
    def test_invalid_hwnd_rejected(self, mock_win):
        el = self._make_el()
        result = safety.check_element_actionable(el)
        assert result.ok is False


class TestControlTypeForAction:
    @patch("automation.safety._is_window", return_value=True)
    def test_click_button_passes(self, _):
        el = {
            "control_type": "Button",
            "is_enabled": True,
            "is_visible": True,
            "bounds": {"width": 100, "height": 40},
            "hwnd": 1,
        }
        result = safety.check_control_type_for_action(el, "click")
        assert result.ok is True

    @patch("automation.safety._is_window", return_value=True)
    def test_type_edit_passes(self, _):
        el = {
            "control_type": "Edit",
            "is_enabled": True,
            "is_visible": True,
            "bounds": {"width": 100, "height": 40},
            "hwnd": 1,
        }
        result = safety.check_control_type_for_action(el, "type")
        assert result.ok is True

    @patch("automation.safety._is_window", return_value=True)
    def test_type_button_rejected(self, _):
        el = {
            "control_type": "Button",
            "is_enabled": True,
            "is_visible": True,
            "bounds": {"width": 100, "height": 40},
            "hwnd": 1,
        }
        result = safety.check_control_type_for_action(el, "type")
        assert result.ok is False
        assert "not editable" in result.reason.lower() or "Edit" in result.reason

    @patch("automation.safety._is_window", return_value=True)
    def test_key_any_element_passes(self, _):
        el = {"control_type": "Text", "hwnd": 1}
        result = safety.check_control_type_for_action(el, "key")
        assert result.ok is True


class TestActionValidatorUnit:
    """Unit tests with mocked UIA revalidation."""

    def setup_method(self):
        self.validator = ActionValidator(check_foreground=False)

    def _make_ref(self, control_type="Button", **kwargs):
        base = {
            "hwnd": 99999,
            "runtime_id": "rid123",
            "automation_id": "aid",
            "control_type": control_type,
            "name": "TestBtn",
            "bounds": {
                "left": 0,
                "top": 0,
                "right": 100,
                "bottom": 40,
                "width": 100,
                "height": 40,
            },
            "window_title": "Test Window",
            "process_id": 1234,
        }
        base.update(kwargs)
        return base

    @patch("automation.action_validator.uia_inspector.revalidate_element")
    @patch("automation.safety._is_window", return_value=True)
    @patch("automation.safety._get_window_class", return_value="SomeClass")
    def test_click_valid_element(self, mock_class, mock_win, mock_revalidate):
        mock_revalidate.return_value = {
            "valid": True,
            "element": {
                "hwnd": 99999,
                "is_enabled": True,
                "is_visible": True,
                "control_type": "Button",
                "name": "TestBtn",
                "bounds": {"width": 100, "height": 40},
            },
            "reason": "Matched",
        }
        ref = self._make_ref("Button")
        result = self.validator.validate_click(ref)
        assert result.ok is True

    @patch("automation.action_validator.uia_inspector.revalidate_element")
    @patch("automation.safety._is_window", return_value=True)
    @patch("automation.safety._get_window_class", return_value="SomeClass")
    def test_type_into_button_rejected(self, mock_class, mock_win, mock_revalidate):
        mock_revalidate.return_value = {
            "valid": True,
            "element": {
                "hwnd": 99999,
                "is_enabled": True,
                "is_visible": True,
                "control_type": "Button",
                "name": "TestBtn",
                "bounds": {"width": 100, "height": 40},
            },
            "reason": "Matched",
        }
        ref = self._make_ref("Button")
        result = self.validator.validate_type(ref, "hello")
        assert result.ok is False
        assert "not editable" in result.reason.lower() or "Edit" in result.reason

    @patch("automation.action_validator.uia_inspector.revalidate_element")
    @patch("automation.safety._is_window", return_value=True)
    @patch("automation.safety._get_window_class", return_value="SomeClass")
    def test_stale_element_rejected(self, mock_class, mock_win, mock_revalidate):
        mock_revalidate.return_value = {
            "valid": False,
            "element": None,
            "reason": "Element not found",
        }
        ref = self._make_ref("Edit")
        result = self.validator.validate_click(ref)
        assert result.ok is False
        assert "revalidation" in result.reason.lower()

    def test_key_enter_passes(self):
        result = self.validator.validate_key("enter")
        assert result.ok is True

    def test_key_unknown_fails(self):
        result = self.validator.validate_key("__badkey__")
        assert result.ok is False
