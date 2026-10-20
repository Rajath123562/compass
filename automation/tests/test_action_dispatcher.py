"""
Tests for automation/action_dispatcher.py
Tests real Windows key dispatch; click/type require a real window.
"""

import sys

import pytest

from automation import action_dispatcher
from automation.models import VK_CODES, ExecutionMethod


class TestSendKey:
    """send_key tests — real Windows SendInput (requires Windows runtime)."""

    def test_send_key_enter_on_windows(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = action_dispatcher.send_key("enter")
        assert result.action_type == "key"
        # Success or fail — must not crash, must return ActionResult
        assert isinstance(result.success, bool)
        assert result.execution_method == ExecutionMethod.SENDINPUT.value

    def test_send_key_unknown_fails(self):
        result = action_dispatcher.send_key("__not_a_key__")
        assert result.success is False
        assert result.error is not None

    def test_send_key_escape(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = action_dispatcher.send_key("escape")
        assert isinstance(result.success, bool)

    def test_send_key_tab(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = action_dispatcher.send_key("tab")
        assert isinstance(result.success, bool)

    def test_send_key_audit_log_id(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = action_dispatcher.send_key("space")
        # log_id may be None if DB not initialized, or int if it is
        assert result.log_id is None or isinstance(result.log_id, int)

    def test_send_key_duration_recorded(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = action_dispatcher.send_key("enter")
        assert result.duration_ms >= 0


class TestActionResult:
    """Unit tests for ActionResult model."""

    def test_to_dict_contains_required_keys(self):
        from automation.models import ActionResult

        r = ActionResult(
            action_type="click",
            success=True,
            execution_method="uia_invoke",
            target_name="Save",
            duration_ms=12.5,
        )
        d = r.to_dict()
        for key in (
            "action_type",
            "success",
            "execution_method",
            "target_name",
            "error",
            "duration_ms",
            "timestamp",
        ):
            assert key in d

    def test_failed_result_has_error(self):
        from automation.models import ActionResult

        r = ActionResult(action_type="type", success=False, error="Target not found")
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "Target not found"


class TestSendVK:
    """Unit test the internal _send_vk function."""

    def test_send_vk_valid_code(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        ok = action_dispatcher._send_vk(0x0D)  # Enter
        assert isinstance(ok, bool)

    def test_send_vk_zero_code(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        # VK code 0 should not crash
        ok = action_dispatcher._send_vk(0)
        assert isinstance(ok, bool)


class TestSafetySaturation:
    """Test that automation respects safety models."""

    def test_models_have_vk_codes(self):
        assert len(VK_CODES) > 20
        assert "enter" in VK_CODES
        assert "escape" in VK_CODES
        assert "tab" in VK_CODES
        assert "backspace" in VK_CODES

    def test_execution_methods_defined(self):
        methods = [e.value for e in ExecutionMethod]
        assert "uia_invoke" in methods
        assert "uia_value" in methods
        assert "sendinput" in methods
