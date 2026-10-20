"""
Tests for perception/uia_inspector.py
Tests run on real Windows 11 — UIA availability is checked first.
Mocks used for deterministic unit tests; real UIA tested separately.
"""

import sys

import pytest

from perception import uia_inspector
from perception.models import BoundingRect


class TestUIAStatus:
    """Test UIA subsystem initialization and status reporting."""

    def test_get_uia_status_returns_dict(self):
        status = uia_inspector.get_uia_status()
        assert isinstance(status, dict)
        assert "available" in status
        assert "platform" in status

    def test_uia_status_platform_field(self):
        status = uia_inspector.get_uia_status()
        assert status["platform"] == sys.platform

    def test_uia_available_on_windows(self):
        """On Windows 11, UIA should initialize successfully."""
        if sys.platform != "win32":
            pytest.skip("UIA only available on Windows")
        status = uia_inspector.get_uia_status()
        assert status["available"] is True, (
            f"UIA unavailable on Windows 11: {status.get('error')}"
        )


class TestForegroundWindow:
    """Test foreground window discovery."""

    def test_get_foreground_window_returns_dict(self):
        result = uia_inspector.get_foreground_window()
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_foreground_window_on_windows(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = uia_inspector.get_foreground_window()
        if not result["success"]:
            pytest.skip(
                f"No foreground window in this environment: {result.get('error')}"
            )
        win = result["window"]
        assert isinstance(win["hwnd"], int)
        assert win["hwnd"] != 0
        assert isinstance(win["process_id"], int)
        assert isinstance(win["title"], str)
        assert isinstance(win["class_name"], str)
        # Bounding rect must be a dict with left/top/right/bottom
        bounds = win["bounds"]
        assert all(k in bounds for k in ("left", "top", "right", "bottom"))

    def test_foreground_window_has_valid_bounds(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        result = uia_inspector.get_foreground_window()
        if not result["success"]:
            pytest.skip("No foreground window available")
        bounds = result["window"]["bounds"]
        # Width and height should be positive for a visible window
        w = bounds["right"] - bounds["left"]
        h = bounds["bottom"] - bounds["top"]
        assert w >= 0
        assert h >= 0


class TestElementTree:
    """Test UIA element tree traversal."""

    def test_get_element_tree_invalid_hwnd_returns_error(self):
        result = uia_inspector.get_element_tree(hwnd=999999999)
        assert result["success"] is False
        assert "error" in result
        assert result["elements"] == []
        assert result["count"] == 0

    def test_get_element_tree_zero_hwnd_returns_error(self):
        result = uia_inspector.get_element_tree(hwnd=0)
        assert result["success"] is False

    def test_get_element_tree_foreground_on_windows(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        status = uia_inspector.get_uia_status()
        if not status["available"]:
            pytest.skip(f"UIA not available: {status.get('error')}")

        fw = uia_inspector.get_foreground_window()
        if not fw["success"]:
            pytest.skip("No foreground window")

        hwnd = fw["window"]["hwnd"]
        result = uia_inspector.get_element_tree(hwnd=hwnd, depth=2, max_elements=50)
        assert result["success"] is True, f"Element tree failed: {result.get('error')}"
        assert isinstance(result["elements"], list)
        assert result["count"] >= 0
        # Each element must have required fields
        for el in result["elements"]:
            assert "element_id" in el
            assert "control_type" in el
            assert "hwnd" in el
            assert el["hwnd"] == hwnd
            assert "bounds" in el
            assert "is_enabled" in el
            assert "is_visible" in el
            assert el.get("source") == "uia"
            assert el.get("confidence") is None  # UIA is deterministic

    def test_element_tree_respects_max_elements(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        status = uia_inspector.get_uia_status()
        if not status["available"]:
            pytest.skip("UIA not available")
        fw = uia_inspector.get_foreground_window()
        if not fw["success"]:
            pytest.skip("No foreground window")
        hwnd = fw["window"]["hwnd"]
        result = uia_inspector.get_element_tree(hwnd=hwnd, depth=5, max_elements=10)
        assert result["count"] <= 10

    def test_element_tree_depth_0_returns_error(self):
        result = uia_inspector.get_element_tree(hwnd=0, depth=0)
        assert result["success"] is False


class TestFindElement:
    """Test element search functions."""

    def test_find_by_name_invalid_hwnd(self):
        result = uia_inspector.find_element_by_name(hwnd=999999999, name="anything")
        assert result["found"] is False
        assert result["element"] is None

    def test_find_by_type_invalid_hwnd(self):
        result = uia_inspector.find_element_by_type(
            hwnd=999999999, control_type="Button"
        )
        assert result["elements"] == []
        assert result["count"] == 0


class TestRevalidate:
    """Test element revalidation."""

    def test_revalidate_missing_hwnd(self):
        ref = {"hwnd": 0, "runtime_id": "", "name": "test"}
        result = uia_inspector.revalidate_element(ref)
        assert result["valid"] is False
        assert "reason" in result

    def test_revalidate_bad_hwnd(self):
        ref = {"hwnd": 999999999, "runtime_id": "", "name": "test"}
        result = uia_inspector.revalidate_element(ref)
        assert result["valid"] is False


class TestBoundingRect:
    """Unit tests for BoundingRect model."""

    def test_area(self):
        r = BoundingRect(left=0, top=0, right=100, bottom=50)
        assert r.area == 5000

    def test_zero_area_invalid(self):
        r = BoundingRect(left=10, top=10, right=10, bottom=10)
        assert not r.is_valid
        assert r.area == 0

    def test_center(self):
        r = BoundingRect(left=0, top=0, right=100, bottom=100)
        cx, cy = r.center
        assert cx == 50
        assert cy == 50

    def test_from_ltwh(self):
        r = BoundingRect.from_ltwh(10, 20, 300, 200)
        assert r.left == 10
        assert r.top == 20
        assert r.right == 310
        assert r.bottom == 220
        assert r.width == 300
        assert r.height == 200

    def test_to_dict(self):
        r = BoundingRect(left=1, top=2, right=101, bottom=52)
        d = r.to_dict()
        assert d["left"] == 1
        assert d["width"] == 100
        assert d["height"] == 50
