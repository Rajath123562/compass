import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ["COMPASS_TEST_MODE"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Fallback mocks for Windows-specific packages if running under Linux (e.g. ChatGPT / CI environment)
for _mod in [
    "winrt",
    "winrt.windows",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.globalization",
    "winrt.windows.graphics",
    "winrt.windows.graphics.imaging",
    "winrt.windows.media",
    "winrt.windows.media.ocr",
    "winrt.windows.storage",
    "winrt.windows.storage.streams",
    "comtypes",
    "comtypes.client",
    "comtypes.gen",
    "comtypes.gen.UIAutomationClient",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]:
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            sys.modules[_mod] = MagicMock()


@pytest.fixture(autouse=True)
def reset_global_state():
    """Ensure global singletons like circuit breakers are reset between tests to prevent test pollution."""
    try:
        from planner.circuit_breaker import ai_circuit_breaker
        ai_circuit_breaker.reset()
    except ImportError:
        pass
    yield
