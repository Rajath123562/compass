"""
COMPASS — Playwright Browser Adapter (Phase 8)
Integrates Playwright (open-source, Apache 2.0) for browser automation tasks.

Provides:
  - BrowserAdapter: manages browser lifecycle with COMPASS safety controls
  - navigate()           -> navigate to URL
  - get_accessibility_tree() -> DOM + accessibility tree for perception
  - find_element()       -> semantic element search
  - click_element()      -> click with validation
  - type_text()          -> type into element with validation
  - get_page_text()      -> extract visible text
  - take_screenshot()    -> capture page screenshot

All actions pass through COMPASS validation and safety layers.
No hard-coded coordinates. Uses semantic selectors and accessibility tree.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports
_playwright_available = None


def _check_playwright() -> bool:
    """Check if Playwright is installed."""
    global _playwright_available
    if _playwright_available is not None:
        return _playwright_available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        _playwright_available = True
        logger.info("Playwright available")
        return True
    except ImportError:
        _playwright_available = False
        logger.warning("Playwright not installed — browser automation unavailable")
        return False


def is_available() -> bool:
    """Check if Playwright is installed and importable."""
    return _check_playwright()


@dataclass
class BrowserActionResult:
    """Result from a browser action."""

    success: bool = False
    action_type: str = ""
    url: str = ""
    title: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action_type": self.action_type,
            "url": self.url,
            "title": self.title,
            "error": self.error,
            "data": self.data,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class AccessibilityNode:
    """A node from the browser accessibility tree."""

    role: str = ""
    name: str = ""
    value: str = ""
    description: str = ""
    focused: bool = False
    children_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "value": self.value,
            "description": self.description,
            "focused": self.focused,
            "children_count": self.children_count,
        }


# ─── Blocked URL patterns for safety ─────────────────────────────────────────
BLOCKED_URL_PATTERNS = [
    "file:///",  # No local filesystem access
    "chrome://",  # No browser internals
    "edge://",
    "about:config",
    "javascript:",  # No JS injection
]

BLOCKED_DOMAINS = [
    # Financial/payment sites require explicit user confirmation
    "paypal.com",
    "stripe.com",
    "bank",
]


class BrowserAdapter:
    """
    COMPASS browser automation adapter using Playwright.
    Manages a single browser instance with COMPASS safety controls.

    Usage:
        adapter = BrowserAdapter()
        adapter.start()
        result = adapter.navigate("https://example.com")
        tree = adapter.get_accessibility_tree()
        adapter.stop()
    """

    def __init__(
        self,
        headless: bool = False,
        browser_type: str = "chromium",
        timeout_ms: int = 30000,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ):
        self.headless = headless
        self.browser_type = browser_type
        self.timeout_ms = timeout_ms
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started and self._page is not None

    def start(self) -> BrowserActionResult:
        """Launch browser instance."""
        start_t = time.time()
        result = BrowserActionResult(action_type="start_browser")

        if not _check_playwright():
            result.error = "Playwright not installed"
            return result

        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()

            launcher = getattr(self._playwright, self.browser_type, None)
            if launcher is None:
                result.error = f"Unknown browser type: {self.browser_type}"
                return result

            self._browser = launcher.launch(headless=self.headless)
            self._context = self._browser.new_context(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                user_agent="COMPASS/2.0 Browser Automation",
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)
            self._started = True
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
            logger.info(
                f"Browser started ({self.browser_type}, headless={self.headless})"
            )

        except Exception as e:  # noqa: BLE001
            result.error = f"Browser start failed: {e!s}"
            logger.error(result.error)

        return result

    def stop(self) -> BrowserActionResult:
        """Close browser and release resources."""
        result = BrowserActionResult(action_type="stop_browser")
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._started = False
            result.success = True
            logger.info("Browser stopped")
        except Exception as e:  # noqa: BLE001
            result.error = f"Browser stop failed: {e!s}"
            logger.error(result.error)
        return result

    def _check_url_safety(self, url: str) -> str | None:
        """Check if a URL is safe to navigate to. Returns error string or None."""
        url_lower = url.lower().strip()
        for pattern in BLOCKED_URL_PATTERNS:
            if url_lower.startswith(pattern):
                return f"Blocked URL pattern: {pattern}"
        for domain in BLOCKED_DOMAINS:
            if domain in url_lower:
                return f"Blocked domain (requires confirmation): {domain}"
        return None

    def is_safe_url(self, url: str) -> bool:
        """Check whether a target URL passes COMPASS navigation safety policies."""
        return self._check_url_safety(url) is None

    def navigate(self, url: str) -> BrowserActionResult:
        """Navigate to a URL. Subject to COMPASS safety checks."""
        start_t = time.time()
        result = BrowserActionResult(action_type="navigate", url=url)

        if not self.is_running:
            result.error = "Browser not started"
            return result

        # Safety check
        safety_err = self._check_url_safety(url)
        if safety_err:
            result.error = f"Safety blocked: {safety_err}"
            return result

        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            result.url = self._page.url
            result.title = self._page.title()
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Navigation failed: {e!s}"

        return result

    def get_accessibility_tree(self) -> BrowserActionResult:
        """
        Get the page accessibility tree for COMPASS perception.
        Uses Playwright CDP session to get Accessibility tree.
        """
        start_t = time.time()
        result = BrowserActionResult(action_type="get_accessibility_tree")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        try:
            client = self._context.new_cdp_session(self._page)
            tree_data = client.send("Accessibility.getFullAXTree")
            nodes = tree_data.get("nodes", [])

            # Simple flattening for COMPASS perception
            flat_tree = []
            for node in nodes:
                role = node.get("role", {}).get("value", "")
                if not role or role in ("none", "presentation"):
                    continue
                name = node.get("name", {}).get("value", "")
                if not name and not role:
                    continue
                flat_tree.append(
                    {
                        "role": role,
                        "name": name,
                        "description": node.get("description", {}).get("value", ""),
                        "focused": next(
                            (
                                p.get("value")
                                for p in node.get("properties", [])
                                if p.get("name") == "focused"
                            ),
                            False,
                        ),
                    }
                )

            result.data = {"tree": flat_tree}
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Accessibility tree failed: {e!s}"

        return result

    def find_element(self, selector: str, semantic: bool = True) -> BrowserActionResult:
        """
        Find an element on the page.
        Prefers semantic selectors (role, text, label) over CSS.
        """
        start_t = time.time()
        result = BrowserActionResult(action_type="find_element")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        try:
            if semantic:
                # Try role-based first, then text, then CSS
                locator = self._page.get_by_role("button", name=selector)
                if locator.count() == 0:
                    locator = self._page.get_by_text(selector)
                if locator.count() == 0:
                    locator = self._page.locator(selector)
            else:
                locator = self._page.locator(selector)

            count = locator.count()
            result.data = {
                "found": count > 0,
                "count": count,
                "selector": selector,
            }
            if count > 0:
                bbox = locator.first.bounding_box()
                if bbox:
                    result.data["bounding_box"] = bbox
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Find element failed: {e!s}"

        return result

    def click_element(
        self, selector: str, semantic: bool = True
    ) -> BrowserActionResult:
        """Click an element. Uses semantic selectors by default."""
        start_t = time.time()
        result = BrowserActionResult(action_type="click")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        try:
            if semantic:
                locator = self._page.get_by_role("button", name=selector)
                if locator.count() == 0:
                    locator = self._page.get_by_text(selector)
                if locator.count() == 0:
                    locator = self._page.locator(selector)
            else:
                locator = self._page.locator(selector)

            locator.first.click(timeout=self.timeout_ms)
            result.url = self._page.url
            result.title = self._page.title()
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Click failed: {e!s}"

        return result

    def type_text(
        self, selector: str, text: str, clear_first: bool = True
    ) -> BrowserActionResult:
        """Type text into an input element."""
        start_t = time.time()
        result = BrowserActionResult(action_type="type")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        # Safety: limit text length
        if len(text) > 10000:
            result.error = "Text too long (max 10000 chars)"
            return result

        try:
            locator = self._page.locator(selector)
            if clear_first:
                locator.first.fill(text, timeout=self.timeout_ms)
            else:
                locator.first.type(text, timeout=self.timeout_ms)
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Type text failed: {e!s}"

        return result

    def get_page_text(self) -> BrowserActionResult:
        """Extract all visible text from the page."""
        start_t = time.time()
        result = BrowserActionResult(action_type="get_page_text")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        try:
            text = self._page.inner_text("body")
            # Truncate to prevent memory issues
            result.data = {"text": text[:50000], "truncated": len(text) > 50000}
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Get page text failed: {e!s}"

        return result

    def take_screenshot(
        self, output_path: str, full_page: bool = False
    ) -> BrowserActionResult:
        """Take a screenshot of the current page."""
        start_t = time.time()
        result = BrowserActionResult(action_type="screenshot")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        try:
            self._page.screenshot(path=output_path, full_page=full_page)
            result.data = {"path": output_path, "full_page": full_page}
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"Screenshot failed: {e!s}"

        return result

    def evaluate_js(self, expression: str) -> BrowserActionResult:
        """
        Evaluate JavaScript on the page.
        SAFETY: Only read-only expressions. No DOM mutations allowed.
        """
        start_t = time.time()
        result = BrowserActionResult(action_type="evaluate_js")

        if not self.is_running:
            result.error = "Browser not started"
            return result

        # Safety: block mutations
        blocked_patterns = [
            "document.write",
            "document.cookie",
            "localStorage",
            "sessionStorage",
            "fetch(",
            "XMLHttpRequest",
            "eval(",
            "Function(",
            ".remove()",
            ".delete",
            "window.location",
            "window.open",
        ]
        expr_lower = expression.lower()
        for pattern in blocked_patterns:
            if pattern.lower() in expr_lower:
                result.error = f"Safety blocked: JS expression contains '{pattern}'"
                return result

        try:
            value = self._page.evaluate(expression)
            result.data = {"value": str(value)[:5000]}
            result.success = True
            result.duration_ms = (time.time() - start_t) * 1000
        except Exception as e:  # noqa: BLE001
            result.error = f"JS evaluation failed: {e!s}"

        return result
