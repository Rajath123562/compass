"""
COMPASS — Playwright Browser Adapter Tests
Tests for automation/browser_adapter.py

Tests cover:
  - Availability detection
  - Safety checks (blocked URLs, blocked JS)
  - Browser lifecycle (start/stop)
  - Navigation
  - Page text extraction
  - Graceful degradation
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from automation.browser_adapter import (
    BrowserActionResult,
    BrowserAdapter,
    is_available,
)


class TestAvailability:
    def test_is_available_returns_bool(self):
        result = is_available()
        assert isinstance(result, bool)


class TestSafetyChecks:
    """Test URL and JS safety validation without launching a browser."""

    def test_blocked_file_url(self):
        adapter = BrowserAdapter()
        err = adapter._check_url_safety("file:///etc/passwd")
        assert err is not None
        assert "Blocked" in err

    def test_blocked_javascript_url(self):
        adapter = BrowserAdapter()
        err = adapter._check_url_safety("javascript:alert(1)")
        assert err is not None

    def test_blocked_chrome_url(self):
        adapter = BrowserAdapter()
        err = adapter._check_url_safety("chrome://settings")
        assert err is not None

    def test_blocked_payment_domain(self):
        adapter = BrowserAdapter()
        err = adapter._check_url_safety("https://www.paypal.com/checkout")
        assert err is not None
        assert "confirmation" in err.lower() or "Blocked" in err

    def test_allowed_url(self):
        adapter = BrowserAdapter()
        err = adapter._check_url_safety("https://example.com")
        assert err is None

    def test_allowed_chatgpt_url(self):
        adapter = BrowserAdapter()
        err = adapter._check_url_safety("https://chatgpt.com")
        assert err is None


class TestBrowserActionResult:
    def test_result_defaults(self):
        r = BrowserActionResult()
        assert r.success is False
        assert r.error == ""

    def test_to_dict(self):
        r = BrowserActionResult(
            success=True, action_type="navigate", url="https://x.com"
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["action_type"] == "navigate"
        assert "url" in d


class TestBrowserNotStarted:
    """Test that all methods return proper errors when browser is not started."""

    def test_navigate_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.navigate("https://example.com")
        assert r.success is False
        assert "not started" in r.error.lower()

    def test_find_element_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.find_element("button")
        assert r.success is False

    def test_click_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.click_element("Submit")
        assert r.success is False

    def test_type_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.type_text("input", "hello")
        assert r.success is False

    def test_get_page_text_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.get_page_text()
        assert r.success is False

    def test_screenshot_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.take_screenshot("test.png")
        assert r.success is False

    def test_evaluate_js_not_started(self):
        adapter = BrowserAdapter()
        r = adapter.evaluate_js("1+1")
        assert r.success is False


class TestJSSafety:
    """Test JavaScript expression safety blocking."""

    def test_blocks_document_write(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        r = adapter.evaluate_js("document.write('hack')")
        assert r.success is False
        assert "Safety blocked" in r.error

    def test_blocks_eval(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        r = adapter.evaluate_js("eval('alert(1)')")
        assert r.success is False

    def test_blocks_fetch(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        r = adapter.evaluate_js("fetch('https://evil.com')")
        assert r.success is False

    def test_blocks_cookie_access(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        r = adapter.evaluate_js("document.cookie")
        assert r.success is False

    def test_allows_safe_expression(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        adapter._page.evaluate.return_value = "test_value"
        r = adapter.evaluate_js("document.title")
        assert r.success is True


class TestTextLengthSafety:
    """Test input text length limits."""

    def test_blocks_oversized_text(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        r = adapter.type_text("input", "A" * 10001)
        assert r.success is False
        assert "too long" in r.error.lower()


class TestNavigationSafety:
    """Test that blocked URLs are rejected during navigation."""

    def test_navigate_blocked_url(self):
        adapter = BrowserAdapter()
        adapter._started = True
        adapter._page = MagicMock()
        r = adapter.navigate("file:///etc/passwd")
        assert r.success is False
        assert "Safety blocked" in r.error


@pytest.mark.skipif(not is_available(), reason="Playwright not installed")
class TestBrowserLifecycle:
    """Integration tests requiring actual Playwright."""

    def test_start_and_stop(self):
        adapter = BrowserAdapter(headless=True)
        start_r = adapter.start()
        assert start_r.success is True
        assert adapter.is_running is True

        stop_r = adapter.stop()
        assert stop_r.success is True
        assert adapter.is_running is False

    def test_navigate_and_get_text(self):
        adapter = BrowserAdapter(headless=True)
        adapter.start()
        try:
            nav = adapter.navigate("https://example.com")
            assert nav.success is True
            assert "example" in nav.title.lower() or nav.url.startswith(
                "https://example"
            )

            text = adapter.get_page_text()
            assert text.success is True
            assert len(text.data.get("text", "")) > 0
        finally:
            adapter.stop()

    def test_screenshot(self, tmp_path):
        adapter = BrowserAdapter(headless=True)
        adapter.start()
        try:
            adapter.navigate("https://example.com")
            out = str(tmp_path / "screenshot.png")
            result = adapter.take_screenshot(out)
            assert result.success is True
            assert Path(out).exists()
        finally:
            adapter.stop()
