"""
COMPASS Win32 Overlay Helper
Uses Python standard library ctypes to configure Windows extended window styles (click-through)
and per-monitor DPI awareness without external dependencies.
"""

import ctypes
import sys
from ctypes import wintypes

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


def set_dpi_awareness() -> bool:
    """Set process-wide Per-Monitor DPI awareness on Windows."""
    if sys.platform != "win32":
        return False
    try:
        # Windows 10/11: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (-4)
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
            res = user32.SetProcessDpiAwarenessContext(
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            )
            if res:
                return True
        # Fallback for earlier Windows builds: shcore.SetProcessDpiAwareness(2)
        if hasattr(ctypes.windll, "shcore") and hasattr(
            ctypes.windll.shcore, "SetProcessDpiAwareness"
        ):
            res = ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return res == 0
    except Exception:  # noqa: BLE001, S110
        pass
    return False


def make_window_click_through(hwnd: int, enable: bool = True) -> bool:
    """
    Apply WS_EX_TRANSPARENT and WS_EX_LAYERED extended styles to hwnd.
    When enabled, mouse clicks pass directly through the overlay window to underlying applications.
    """
    if sys.platform != "win32" or not hwnd:
        return False

    try:
        user32 = ctypes.windll.user32

        # Determine 32-bit vs 64-bit GetWindowLong/SetWindowLong
        if sys.maxsize > 2**32:
            # 64-bit Windows
            GetWindowLong = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            SetWindowLong = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            GetWindowLong.restype = ctypes.c_longlong
            GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
            SetWindowLong.restype = ctypes.c_longlong
            SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
        else:
            # 32-bit Windows
            GetWindowLong = user32.GetWindowLongW
            SetWindowLong = user32.SetWindowLongW
            GetWindowLong.restype = ctypes.c_long
            GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
            SetWindowLong.restype = ctypes.c_long
            SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

        current_style = GetWindowLong(hwnd, GWL_EXSTYLE)
        if enable:
            new_style = current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            new_style = current_style & ~WS_EX_TRANSPARENT

        res = SetWindowLong(hwnd, GWL_EXSTYLE, new_style)
        return res != 0 or current_style == new_style
    except Exception as e:  # noqa: BLE001
        print(f"Error setting click-through style on hwnd {hwnd}: {e}", file=sys.stderr)
        return False


def is_window_click_through(hwnd: int) -> bool:
    """Check if hwnd has the WS_EX_TRANSPARENT style applied."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        if sys.maxsize > 2**32:
            GetWindowLong = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            GetWindowLong.restype = ctypes.c_longlong
            GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
        else:
            GetWindowLong = user32.GetWindowLongW
            GetWindowLong.restype = ctypes.c_long
            GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]

        style = GetWindowLong(hwnd, GWL_EXSTYLE)
        return bool(style & WS_EX_TRANSPARENT)
    except Exception:  # noqa: BLE001
        return False


DWMWA_CLOAKED = 14


def is_real_visible_desktop_window(hwnd: int) -> bool:
    """Filter out invisible, cloaked (DWMWA_CLOAKED), and 0-dimension windows."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        if not user32.IsWindowVisible(hwnd):
            return False
        cloaked = ctypes.c_int(0)
        hr = dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_CLOAKED),
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )
        if hr == 0 and cloaked.value != 0:
            return False
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return False
        return (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0
    except Exception:
        return False

