"""
COMPASS Screen Provider
Wraps screen capture as a pluggable provider.
"""

from pathlib import Path
from typing import Any

from perception import screen_capture
from perception.models import BoundingRect, CaptureResult


class ScreenProvider:
    """Screen capture provider — GDI-based, no external capture library required."""

    name = "gdi_screen"
    description = "Windows GDI screen capture — zero external dependencies"

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        save_dir: Path | None = None,
        include_b64: bool = True,
    ) -> CaptureResult:
        return screen_capture.capture_region(x, y, width, height, save_dir, include_b64)

    def capture_foreground(
        self,
        save_dir: Path | None = None,
        include_b64: bool = False,
    ) -> CaptureResult:
        return screen_capture.capture_foreground_window(save_dir, include_b64)

    def capture_element(
        self,
        bounds: BoundingRect,
        save_dir: Path | None = None,
        include_b64: bool = True,
    ) -> CaptureResult:
        return screen_capture.capture_element_rect(bounds, save_dir, include_b64)

    def capture_full_screen(
        self,
        save_dir: Path | None = None,
        include_b64: bool = False,
    ) -> CaptureResult:
        return screen_capture.capture_full_screen(save_dir, include_b64)

    def get_capabilities(self) -> dict[str, Any]:
        return screen_capture.get_capture_capabilities()


# Module-level singleton
screen_provider = ScreenProvider()
