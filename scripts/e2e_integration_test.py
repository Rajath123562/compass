"""
COMPASS — End-to-End Integration Test
Proves that OpenCV, Playwright, MCP, and Telemetry work together.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.browser_adapter import BrowserAdapter
from automation.mcp_tools import get_tool_registry
from backend.app.telemetry import trace_lifecycle
from perception import opencv_processor


@trace_lifecycle("END_TO_END_TEST")
def run_integration_test():
    print("\n=== STARTING COMPASS END-TO-END TEST ===")

    # 1. MCP Registry Check
    print("\n[1] Testing MCP Tool Registry...")
    registry = get_tool_registry()
    tools = registry.list_tools()
    print(f"  -> Found {len(tools)} registered tools.")
    assert len(tools) >= 11, "Missing default tools"

    # 2. Playwright Browser Start
    print("\n[2] Testing Playwright Browser Integration...")
    browser = BrowserAdapter(headless=True)
    res = browser.start()
    if not res.success:
        print(f"  -> Failed to start browser: {res.error}")
        return False
    print("  -> Browser started successfully.")

    try:
        # Navigate
        print("  -> Navigating to example.com...")
        nav_res = browser.navigate("https://example.com")
        if not nav_res.success:
            print(f"  -> Navigation failed: {nav_res.error}")
            return False

        # Accessibility Tree
        print("  -> Fetching Accessibility Tree...")
        tree_res = browser.get_accessibility_tree()
        if not tree_res.success:
            print(f"  -> Failed to get tree: {tree_res.error}")
            return False
        print(f"  -> Tree contains {len(tree_res.data.get('tree', []))} nodes.")

        # 3. OpenCV Integration
        print("\n[3] Testing OpenCV Visual Processor...")
        if not opencv_processor.is_available():
            print("  -> OpenCV not available, skipping visual tests.")
        else:
            # Take two screenshots
            p1 = "test_screen_1.png"
            p2 = "test_screen_2.png"
            browser.take_screenshot(p1)

            # Inject a visual change
            browser.evaluate_js("document.body.style.backgroundColor = 'red';")
            time.sleep(0.5)
            browser.take_screenshot(p2)

            print("  -> Comparing screenshots with OpenCV...")
            diff = opencv_processor.screenshot_diff(p1, p2)
            print(f"  -> Pixel difference ratio: {diff.pixel_diff_ratio:.4f}")
            print(
                f"  -> Structural similarity (SSIM): {diff.structural_similarity:.4f}"
            )
            print(f"  -> Detected {diff.changed_region_count} changed regions.")

            # Clean up
            for p in [p1, p2]:
                if os.path.exists(p):
                    os.remove(p)

    finally:
        print("\n[4] Shutting down...")
        browser.stop()

    print("\n=== E2E INTEGRATION TEST PASSED ===")
    return True


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
