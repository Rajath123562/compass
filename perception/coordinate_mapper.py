"""
COMPASS Phase 7 — Coordinate & DPI Mapper
Handles DPI scaling, multi-monitor topologies (including negative coordinates),
coordinate space transformations, and safety bounds validation (Section 10).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from dataclasses import dataclass
from typing import Any

from perception.models_multimodal import BoundingBox, CoordinateSpace


@dataclass
class MonitorInfo:
    """Represents a physical or virtual display monitor."""

    monitor_id: int
    hmonitor: int
    is_primary: bool
    bounds: BoundingBox  # Physical screen bounds
    work_area: BoundingBox  # Excluding taskbars/docked bars
    dpi: int = 96  # Standard 100% = 96 DPI
    scale_factor: float = 1.0  # 1.0 = 100%, 1.25 = 125%, 1.5 = 150%, etc.

    def contains(self, x: int, y: int) -> bool:
        return self.bounds.contains_point(x, y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "monitor_id": self.monitor_id,
            "hmonitor": self.hmonitor,
            "is_primary": self.is_primary,
            "bounds": self.bounds.to_dict(),
            "work_area": self.work_area.to_dict(),
            "dpi": self.dpi,
            "scale_factor": self.scale_factor,
        }


class CoordinateMapper:
    """
    Manages coordinate transformations across physical, logical DPI, and window spaces.
    Validates targets to ensure clicks do not land out-of-bounds or on unintended screens.
    """

    def __init__(self):
        self._user32 = None
        self._shcore = None
        self._is_windows = sys.platform == "win32"
        if self._is_windows:
            try:
                self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            except Exception:  # noqa: BLE001
                self._user32 = None
            try:
                self._shcore = ctypes.WinDLL("shcore", use_last_error=True)
            except Exception:  # noqa: BLE001
                self._shcore = None

    def get_virtual_screen_bounds(self) -> BoundingBox:
        """Returns the virtual screen bounding box spanning all monitors (Section 9, 10)."""
        if not self._is_windows or not self._user32:
            return BoundingBox.from_ltwh(0, 0, 1920, 1080)

        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79

        x = self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        y = self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        w = self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        h = self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        if w > 0 and h > 0:
            return BoundingBox.from_ltwh(x, y, w, h, CoordinateSpace.SCREEN_PHYSICAL)

        # Fallback to primary
        pw = self._user32.GetSystemMetrics(0)
        ph = self._user32.GetSystemMetrics(1)
        return BoundingBox.from_ltwh(
            0, 0, max(1, pw), max(1, ph), CoordinateSpace.SCREEN_PHYSICAL
        )

    def get_monitors(self) -> list[MonitorInfo]:
        """Enumerate all connected monitors with their bounds, DPI, and scaling factors."""
        monitors: list[MonitorInfo] = []
        if not self._is_windows or not self._user32:
            # Synthetic default monitor for non-windows / fallback
            monitors.append(
                MonitorInfo(
                    monitor_id=0,
                    hmonitor=1,
                    is_primary=True,
                    bounds=BoundingBox.from_ltwh(0, 0, 1920, 1080),
                    work_area=BoundingBox.from_ltwh(0, 0, 1920, 1040),
                    dpi=96,
                    scale_factor=1.0,
                )
            )
            return monitors

        # Win32 EnumDisplayMonitors callback
        CCHDEVICENAME = 32

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.DWORD),
                ("rcMonitor", ctypes.wintypes.RECT),
                ("rcWork", ctypes.wintypes.RECT),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("szDevice", ctypes.c_wchar * CCHDEVICENAME),
            ]

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL,
            ctypes.wintypes.HMONITOR,
            ctypes.wintypes.HDC,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.wintypes.LPARAM,
        )

        monitor_list = []

        def _enum_proc(hmonitor, hdc, lprect, lparam):
            monitor_list.append(hmonitor)
            return True

        callback = MONITORENUMPROC(_enum_proc)
        try:
            self._user32.EnumDisplayMonitors(0, 0, callback, 0)
        except Exception:  # noqa: BLE001, S110
            pass

        for idx, hmon in enumerate(monitor_list):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            is_pri = False
            dpi = 96
            scale = 1.0

            if self._user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                is_pri = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY = 1
                b = BoundingBox(
                    left=info.rcMonitor.left,
                    top=info.rcMonitor.top,
                    right=info.rcMonitor.right,
                    bottom=info.rcMonitor.bottom,
                    coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
                )
                w = BoundingBox(
                    left=info.rcWork.left,
                    top=info.rcWork.top,
                    right=info.rcWork.right,
                    bottom=info.rcWork.bottom,
                    coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
                )
            else:
                b = BoundingBox.from_ltwh(0, 0, 1920, 1080)
                w = BoundingBox.from_ltwh(0, 0, 1920, 1040)

            # Query DPI for monitor if shcore is available
            # MDT_EFFECTIVE_DPI = 0
            if self._shcore and hasattr(self._shcore, "GetDpiForMonitor"):
                try:
                    dpi_x = ctypes.wintypes.UINT()
                    dpi_y = ctypes.wintypes.UINT()
                    hr = self._shcore.GetDpiForMonitor(
                        hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
                    )
                    if hr == 0 and dpi_x.value > 0:
                        dpi = dpi_x.value
                        scale = dpi / 96.0
                except Exception:  # noqa: BLE001, S110
                    pass

            monitors.append(
                MonitorInfo(
                    monitor_id=idx,
                    hmonitor=int(hmon),
                    is_primary=is_pri,
                    bounds=b,
                    work_area=w,
                    dpi=dpi,
                    scale_factor=scale,
                )
            )

        if not monitors:
            monitors.append(
                MonitorInfo(
                    monitor_id=0,
                    hmonitor=1,
                    is_primary=True,
                    bounds=BoundingBox.from_ltwh(0, 0, 1920, 1080),
                    work_area=BoundingBox.from_ltwh(0, 0, 1920, 1040),
                    dpi=96,
                    scale_factor=1.0,
                )
            )
        return monitors

    def get_monitor_for_point(self, x: int, y: int) -> MonitorInfo | None:
        """Identify which monitor contains a given (x, y) coordinate."""
        for mon in self.get_monitors():
            if mon.contains(x, y):
                return mon
        return None

    def transform_box(
        self,
        box: BoundingBox,
        target_space: CoordinateSpace,
        window_bounds: BoundingBox | None = None,
        dpi_scale: float = 1.0,
    ) -> BoundingBox:
        """
        Transforms a bounding box between CoordinateSpaces:
        - SCREEN_PHYSICAL
        - SCREEN_LOGICAL_DPI
        - WINDOW_RELATIVE
        """
        if box.coordinate_space == target_space:
            return box

        # 1. Normalize from source space to SCREEN_PHYSICAL
        if box.coordinate_space == CoordinateSpace.SCREEN_LOGICAL_DPI:
            scale = dpi_scale if dpi_scale > 0 else 1.0
            phys_left = int(box.left * scale)
            phys_top = int(box.top * scale)
            phys_right = int(box.right * scale)
            phys_bottom = int(box.bottom * scale)
        elif box.coordinate_space == CoordinateSpace.WINDOW_RELATIVE and window_bounds:
            phys_left = window_bounds.left + box.left
            phys_top = window_bounds.top + box.top
            phys_right = window_bounds.left + box.right
            phys_bottom = window_bounds.top + box.bottom
        else:
            phys_left, phys_top, phys_right, phys_bottom = (
                box.left,
                box.top,
                box.right,
                box.bottom,
            )

        # 2. Convert from SCREEN_PHYSICAL to target_space
        if target_space == CoordinateSpace.SCREEN_LOGICAL_DPI:
            scale = dpi_scale if dpi_scale > 0 else 1.0
            return BoundingBox(
                left=int(phys_left / scale),
                top=int(phys_top / scale),
                right=int(phys_right / scale),
                bottom=int(phys_bottom / scale),
                coordinate_space=CoordinateSpace.SCREEN_LOGICAL_DPI,
            )
        elif target_space == CoordinateSpace.WINDOW_RELATIVE and window_bounds:
            return BoundingBox(
                left=phys_left - window_bounds.left,
                top=phys_top - window_bounds.top,
                right=phys_right - window_bounds.left,
                bottom=phys_bottom - window_bounds.top,
                coordinate_space=CoordinateSpace.WINDOW_RELATIVE,
            )
        else:
            return BoundingBox(
                left=phys_left,
                top=phys_top,
                right=phys_right,
                bottom=phys_bottom,
                coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
            )

    def validate_target_point(
        self, x: int, y: int, expected_window_bounds: BoundingBox | None = None
    ) -> tuple[bool, str]:
        """
        Validate that target (x, y) coordinates:
        1. Reside inside the valid multi-monitor virtual screen bounds.
        2. If window bounds are specified, reside inside that window.
        """
        vscreen = self.get_virtual_screen_bounds()
        if not vscreen.contains_point(x, y):
            return (
                False,
                f"Target point ({x}, {y}) is outside virtual screen bounds: {vscreen.to_dict()}",
            )

        if expected_window_bounds and expected_window_bounds.is_valid:  # noqa: SIM102
            if not expected_window_bounds.contains_point(x, y):
                return (
                    False,
                    f"Target point ({x}, {y}) is outside expected window bounds: {expected_window_bounds.to_dict()}",
                )

        return True, "Valid"


def get_system_dpi() -> int:
    """Gets the system DPI."""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        hdc = user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        user32.ReleaseDC(0, hdc)
        return dpi
    except Exception:
        return 96


def physical_to_logical(physical_value: int, dpi: int = 96) -> int:
    """Converts a physical pixel value to a logical one based on DPI."""
    if dpi <= 0:
        dpi = 96
    return int((physical_value * 96) / dpi)


def logical_to_physical(logical_value: int, dpi: int = 96) -> int:
    """Converts a logical pixel value to a physical one based on DPI."""
    if dpi <= 0:
        dpi = 96
    return int((logical_value * dpi) / 96)


def scale_bounds(bounds: Any, source_dpi: int, target_dpi: int) -> Any:
    """Scales CoordinateBounds from a source DPI to a target DPI."""
    from perception.models import CoordinateBounds

    if source_dpi == target_dpi or target_dpi <= 0 or source_dpi <= 0:
        return CoordinateBounds(
            left=bounds.left,
            top=bounds.top,
            right=bounds.right,
            bottom=bounds.bottom,
            coordinate_space=getattr(bounds, "coordinate_space", "LOGICAL"),
            monitor_dpi=target_dpi,
        )

    scale_factor = target_dpi / source_dpi
    return CoordinateBounds(
        left=int(bounds.left * scale_factor),
        top=int(bounds.top * scale_factor),
        right=int(bounds.right * scale_factor),
        bottom=int(bounds.bottom * scale_factor),
        coordinate_space=getattr(bounds, "coordinate_space", "LOGICAL"),
        monitor_dpi=target_dpi,
    )
