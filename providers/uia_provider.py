"""
COMPASS UIA Provider
Wraps the UIA inspector as a pluggable perception provider.

Implements the PerceptionProvider interface — designed for future
OmniRoute/AI planner integration without restructuring.
"""

from typing import Any

from perception import uia_inspector


class UIAProvider:
    """
    Perception provider backed by Windows UI Automation.

    Future providers (OCR, OmniParser) would implement the same interface
    and could be composed with this provider in a unified UI state.
    """

    name = "uia"
    description = "Windows UI Automation — deterministic structural perception"

    def get_foreground_window(self) -> dict[str, Any]:
        return uia_inspector.get_foreground_window()

    def get_element_tree(
        self,
        hwnd: int,
        depth: int = 3,
        max_elements: int = 200,
        timeout_sec: float = 5.0,
    ) -> dict[str, Any]:
        return uia_inspector.get_element_tree(hwnd, depth, max_elements, timeout_sec)

    def find_by_name(self, hwnd: int, name: str, exact: bool = False) -> dict[str, Any]:
        return uia_inspector.find_element_by_name(hwnd, name, exact)

    def find_by_type(self, hwnd: int, control_type: str) -> dict[str, Any]:
        return uia_inspector.find_element_by_type(hwnd, control_type)

    def revalidate(self, element_ref: dict[str, Any]) -> dict[str, Any]:
        return uia_inspector.revalidate_element(element_ref)

    def get_status(self) -> dict[str, Any]:
        return uia_inspector.get_uia_status()


# Module-level singleton
uia_provider = UIAProvider()
