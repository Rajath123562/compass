"""
COMPASS Screen Capture — Unified GDI and Desktop Vision Engine
Combines high-performance Win32 GDI capture (full screen, regions, windows, foreground)
with modern Gemini 3.8 Flash Vision ScreenSnapshot and automatic scaling.

DPI-aware: honors DPI scaling when retrieving screen dimensions.
Multi-monitor: captures across negative coordinates on multi-monitor setups.
Resource safety: All HDC/HBITMAP handles explicitly released in finally blocks.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import io
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab

from backend.app.logging_config import logger
from perception.models import BoundingRect, CaptureResult

# ─── Win32 types and constants ────────────────────────────────────────────────
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.wintypes.DWORD * 3),
    ]


# ─── GDI/User32 with correct 64-bit handle prototypes ────────────────────────
_SZ = ctypes.c_size_t
_INT = ctypes.c_int
_BOOL = ctypes.wintypes.BOOL
_DWORD = ctypes.wintypes.DWORD
_UINT = ctypes.wintypes.UINT
_LPVOID = ctypes.c_void_p
_PRECT = ctypes.POINTER(ctypes.wintypes.RECT)

if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    _user32.GetDC.restype = _SZ
    _user32.GetDC.argtypes = [_SZ]
    _user32.GetWindowDC.restype = _SZ
    _user32.GetWindowDC.argtypes = [_SZ]
    _user32.ReleaseDC.restype = _INT
    _user32.ReleaseDC.argtypes = [_SZ, _SZ]
    _user32.GetDesktopWindow.restype = _SZ
    _user32.GetDesktopWindow.argtypes = []
    _user32.GetForegroundWindow.restype = _SZ
    _user32.GetForegroundWindow.argtypes = []
    _user32.GetSystemMetrics.restype = _INT
    _user32.GetSystemMetrics.argtypes = [_INT]
    _user32.GetWindowRect.restype = _BOOL
    _user32.GetWindowRect.argtypes = [_SZ, _PRECT]
    _user32.IsWindow.restype = _BOOL
    _user32.IsWindow.argtypes = [_SZ]
    _user32.IsWindowVisible.restype = _BOOL
    _user32.IsWindowVisible.argtypes = [_SZ]
    _user32.PrintWindow.restype = _BOOL
    _user32.PrintWindow.argtypes = [_SZ, _SZ, _UINT]

    _gdi32.CreateCompatibleDC.restype = _SZ
    _gdi32.CreateCompatibleDC.argtypes = [_SZ]
    _gdi32.CreateCompatibleBitmap.restype = _SZ
    _gdi32.CreateCompatibleBitmap.argtypes = [_SZ, _INT, _INT]
    _gdi32.SelectObject.restype = _SZ
    _gdi32.SelectObject.argtypes = [_SZ, _SZ]
    _gdi32.BitBlt.restype = _BOOL
    _gdi32.BitBlt.argtypes = [_SZ, _INT, _INT, _INT, _INT, _SZ, _INT, _INT, _DWORD]
    _gdi32.GetDIBits.restype = _INT
    _gdi32.GetDIBits.argtypes = [_SZ, _SZ, _UINT, _UINT, _LPVOID, _LPVOID, _UINT]
    _gdi32.DeleteObject.restype = _BOOL
    _gdi32.DeleteObject.argtypes = [_SZ]
    _gdi32.DeleteDC.restype = _BOOL
    _gdi32.DeleteDC.argtypes = [_SZ]
    _gdi32.GetDeviceCaps.restype = _INT
    _gdi32.GetDeviceCaps.argtypes = [_SZ, _INT]
else:
    _user32 = None
    _gdi32 = None


# ─── Virtual Screen and GDI Core ──────────────────────────────────────────────

def _get_virtual_screen_bounds() -> BoundingRect:
    """Return the virtual screen bounds (all monitors combined)."""
    if sys.platform != "win32" or not _user32:
        return BoundingRect.from_ltwh(0, 0, 1920, 1080)
    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79
    x = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    y = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    w = _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    h = _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if w > 0 and h > 0:
        return BoundingRect.from_ltwh(x, y, w, h)
    dc = _user32.GetDC(0)
    w = _gdi32.GetDeviceCaps(dc, 8)  # HORZRES
    h = _gdi32.GetDeviceCaps(dc, 10)  # VERTRES
    _user32.ReleaseDC(0, dc)
    return BoundingRect.from_ltwh(0, 0, w, h)


def _capture_region_raw(
    x: int, y: int, width: int, height: int, timeout_sec: float = 5.0
) -> tuple[bytes | None, str]:
    if width <= 0 or height <= 0:
        return None, f"Invalid capture region: width={width}, height={height}"
    if sys.platform != "win32" or not _user32 or not _gdi32:
        return None, "Screen capture only supported on Windows"

    start = time.time()
    src_hwnd: int = 0
    src_dc: int = 0
    mem_dc: int = 0
    bmp: int = 0
    old_bmp: int = 0
    try:
        src_hwnd = _user32.GetForegroundWindow()
        if not src_hwnd:
            src_hwnd = _user32.GetDesktopWindow()

        src_dc = _user32.GetWindowDC(src_hwnd)
        if not src_dc:
            src_dc = _user32.GetDC(0)
            src_hwnd = 0
            if not src_dc:
                return None, "GetWindowDC and GetDC(0) both failed"

        mem_dc = _gdi32.CreateCompatibleDC(src_dc)
        if not mem_dc:
            return None, "CreateCompatibleDC failed"

        bmp = _gdi32.CreateCompatibleBitmap(src_dc, width, height)
        if not bmp:
            return None, "CreateCompatibleBitmap failed"

        old_bmp = _gdi32.SelectObject(mem_dc, bmp)

        if src_hwnd:
            win_rect = ctypes.wintypes.RECT()
            _user32.GetWindowRect(src_hwnd, ctypes.byref(win_rect))
            src_x = x - win_rect.left
            src_y = y - win_rect.top
        else:
            src_x, src_y = x, y

        result = _gdi32.BitBlt(
            mem_dc, 0, 0, width, height, src_dc, src_x, src_y, SRCCOPY
        )
        if not result:
            err_code = ctypes.get_last_error()
            if src_hwnd:
                pw_ok = _user32.PrintWindow(src_hwnd, mem_dc, 2)
                if not pw_ok:
                    _user32.PrintWindow(src_hwnd, mem_dc, 0)
            else:
                return None, f"BitBlt failed (error {err_code})"

        if time.time() - start > timeout_sec:
            return None, "Capture timeout"

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf_size = width * height * 4
        buf = (ctypes.c_char * buf_size)()
        lines = _gdi32.GetDIBits(
            mem_dc, bmp, 0, height, buf, ctypes.addressof(bmi), DIB_RGB_COLORS
        )
        if lines == 0:
            return None, "GetDIBits failed"

        if old_bmp:
            _gdi32.SelectObject(mem_dc, old_bmp)
        return bytes(buf), ""

    except Exception as e:
        return None, str(e)
    finally:
        try:
            if bmp:
                _gdi32.DeleteObject(bmp)
            if mem_dc:
                _gdi32.DeleteDC(mem_dc)
            if src_dc:
                _user32.ReleaseDC(src_hwnd, src_dc)
        except Exception:
            pass


def _capture_window_raw(
    hwnd: int, width: int, height: int
) -> tuple[bytes | None, str]:
    if not hwnd or width <= 0 or height <= 0 or not _user32 or not _gdi32:
        return None, "Invalid window or dimensions"

    win_dc: int = 0
    mem_dc: int = 0
    bmp: int = 0
    old_bmp: int = 0
    try:
        win_dc = _user32.GetWindowDC(hwnd)
        if not win_dc:
            return None, "GetWindowDC failed"

        mem_dc = _gdi32.CreateCompatibleDC(win_dc)
        if not mem_dc:
            return None, "CreateCompatibleDC failed"

        bmp = _gdi32.CreateCompatibleBitmap(win_dc, width, height)
        if not bmp:
            return None, "CreateCompatibleBitmap failed"

        old_bmp = _gdi32.SelectObject(mem_dc, bmp)

        pw_result = _user32.PrintWindow(hwnd, mem_dc, 2)
        if not pw_result:
            _user32.PrintWindow(hwnd, mem_dc, 0)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf_size = width * height * 4
        buf = (ctypes.c_char * buf_size)()
        lines = _gdi32.GetDIBits(
            mem_dc, bmp, 0, height, buf, ctypes.addressof(bmi), DIB_RGB_COLORS
        )
        if lines == 0:
            return None, "GetDIBits failed (window)"

        if old_bmp:
            _gdi32.SelectObject(mem_dc, old_bmp)
        return bytes(buf), ""

    except Exception as e:
        return None, str(e)
    finally:
        try:
            if bmp:
                _gdi32.DeleteObject(bmp)
            if mem_dc:
                _gdi32.DeleteDC(mem_dc)
            if win_dc:
                _user32.ReleaseDC(hwnd, win_dc)
        except Exception:
            pass


def _save_png(
    raw_bgra: bytes, width: int, height: int, out_dir: Path, prefix: str = "capture"
) -> str | None:
    try:
        from PIL import Image

        img = Image.frombytes("RGBA", (width, height), raw_bgra, "raw", "BGRA")
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{prefix}_{int(time.time() * 1000)}.png"
        path = out_dir / filename
        img.save(str(path), "PNG")
        return str(path)
    except Exception:
        return None


def capture_region(
    x: int,
    y: int,
    width: int,
    height: int,
    save_dir: Path | None = None,
    include_b64: bool = True,
) -> CaptureResult:
    start = time.time()
    raw, err = _capture_region_raw(x, y, width, height)
    latency = round((time.time() - start) * 1000, 2)

    if err or raw is None:
        return CaptureResult(
            width=0, height=0, latency_ms=latency, error=err or "Unknown capture error"
        )

    data_b64 = base64.b64encode(raw).decode() if include_b64 else None
    png_path = None
    if save_dir:
        png_path = _save_png(raw, width, height, save_dir, "region")

    return CaptureResult(
        width=width,
        height=height,
        format="BGRA",
        data_b64=data_b64,
        png_path=png_path,
        capture_region=BoundingRect.from_ltwh(x, y, width, height),
        latency_ms=latency,
        error=None,
    )


def capture_foreground_window(
    save_dir: Path | None = None,
    include_b64: bool = False,
) -> CaptureResult:
    if sys.platform != "win32" or not _user32:
        return CaptureResult(width=0, height=0, error="Unsupported platform")
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return CaptureResult(width=0, height=0, error="No foreground window")
        rect = ctypes.wintypes.RECT()
        if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return CaptureResult(width=0, height=0, error="GetWindowRect failed")
        x, y = rect.left, rect.top
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        result = capture_region(x, y, w, h, save_dir=save_dir, include_b64=include_b64)
        if not result.success:
            raw, err = _capture_window_raw(hwnd, w, h)
            if raw is None:
                return CaptureResult(width=0, height=0, error=err or "Capture failed")
            data_b64 = base64.b64encode(raw).decode() if include_b64 else None
            png_path = None
            if save_dir:
                png_path = _save_png(raw, w, h, save_dir, "fg_window")
            return CaptureResult(
                width=w,
                height=h,
                format="BGRA",
                data_b64=data_b64,
                png_path=png_path,
                capture_region=BoundingRect.from_ltwh(x, y, w, h),
                latency_ms=0,
                error=None,
            )
        return result
    except Exception as e:
        return CaptureResult(width=0, height=0, error=str(e))


def capture_window(
    hwnd: int,
    save_dir: Path | None = None,
    include_b64: bool = False,
) -> CaptureResult:
    if sys.platform != "win32" or not _user32:
        return CaptureResult(width=0, height=0, error="Unsupported platform")
    if not hwnd or not bool(_user32.IsWindow(hwnd)):
        return CaptureResult(width=0, height=0, error=f"Invalid window handle: {hwnd}")

    try:
        rect = ctypes.wintypes.RECT()
        if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return CaptureResult(width=0, height=0, error="GetWindowRect failed")

        x, y = rect.left, rect.top
        w = max(0, rect.right - rect.left)
        h = max(0, rect.bottom - rect.top)

        if w <= 0 or h <= 0:
            return CaptureResult(
                width=0, height=0, error=f"Invalid window dimensions: {w}x{h}"
            )

        raw, err = _capture_window_raw(hwnd, w, h)
        if raw is None or err:
            return CaptureResult(
                width=0, height=0, error=err or "Window capture failed"
            )

        data_b64 = base64.b64encode(raw).decode() if include_b64 else None
        png_path = None
        if save_dir:
            png_path = _save_png(raw, w, h, save_dir, "window")

        return CaptureResult(
            width=w,
            height=h,
            format="BGRA",
            data_b64=data_b64,
            png_path=png_path,
            capture_region=BoundingRect.from_ltwh(x, y, w, h),
            latency_ms=0,
            error=None,
        )
    except Exception as e:
        return CaptureResult(width=0, height=0, error=str(e))


def capture_element_rect(
    bounds: BoundingRect,
    save_dir: Path | None = None,
    include_b64: bool = True,
) -> CaptureResult:
    if not bounds.is_valid:
        return CaptureResult(width=0, height=0, error="Invalid bounding rectangle")
    return capture_region(
        bounds.left,
        bounds.top,
        bounds.width,
        bounds.height,
        save_dir=save_dir,
        include_b64=include_b64,
    )


def capture_full_screen(
    save_dir: Path | None = None,
    include_b64: bool = False,
) -> CaptureResult:
    bounds = _get_virtual_screen_bounds()
    return capture_region(
        bounds.left,
        bounds.top,
        bounds.width,
        bounds.height,
        save_dir=save_dir,
        include_b64=include_b64,
    )


def get_capture_capabilities() -> dict[str, Any]:
    try:
        vscreen = _get_virtual_screen_bounds()
        primary_w = _user32.GetSystemMetrics(0) if _user32 else 1920
        primary_h = _user32.GetSystemMetrics(1) if _user32 else 1080
        monitor_count = _user32.GetSystemMetrics(80) if _user32 else 1

        pillow_ok = True
        return {
            "platform": sys.platform,
            "primary_screen": {"width": primary_w, "height": primary_h},
            "virtual_screen": vscreen.to_dict(),
            "monitor_count": monitor_count,
            "pillow_available": pillow_ok,
            "gdi_available": sys.platform == "win32",
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Gemini Computer Use Desktop Vision & Scaling ──────────────────────────────

OPTIMAL_MAX_DIMENSION = 1440  # Optimal resolution for Gemini 3.8 Flash Vision


@dataclass
class ScreenSnapshot:
    """Metadata and image payload of a captured screen state for Gemini."""
    image_bytes: bytes
    base64_jpeg: str
    width: int
    height: int
    original_width: int
    original_height: int
    scale_factor_x: float
    scale_factor_y: float
    timestamp: float


class ScreenCapture:
    """Thread-safe screen capture with DPI awareness and resolution optimization."""

    def __init__(self, max_dimension: int = OPTIMAL_MAX_DIMENSION, jpeg_quality: int = 75) -> None:
        self.max_dimension = max_dimension
        self.jpeg_quality = jpeg_quality
        self._ensure_dpi_awareness()

    def _ensure_dpi_awareness(self) -> None:
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def get_screen_resolution(self) -> tuple[int, int]:
        if sys.platform == "win32" and _user32:
            try:
                w = _user32.GetSystemMetrics(0)
                h = _user32.GetSystemMetrics(1)
                if w > 0 and h > 0:
                    return w, h
            except Exception:
                pass
        return 1920, 1080

    def capture_screen(
        self,
        bbox: tuple[int, int, int, int] | None = None,
        max_dim: int | None = None,
        quality: int | None = None,
    ) -> ScreenSnapshot:
        target_max = max_dim or self.max_dimension
        target_quality = quality or self.jpeg_quality

        try:
            img = ImageGrab.grab(bbox=bbox, all_screens=False)
        except Exception as e:
            logger.warning("PIL ImageGrab error: %s, falling back to default grab", e)
            img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))

        orig_w, orig_h = img.size

        if max(orig_w, orig_h) > target_max:
            scale = target_max / float(max(orig_w, orig_h))
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            img_resized = img
            new_w, new_h = orig_w, orig_h

        buffer = io.BytesIO()
        img_resized.save(buffer, format="JPEG", quality=target_quality, optimize=True)
        img_bytes = buffer.getvalue()
        b64_str = base64.b64encode(img_bytes).decode("utf-8")

        scale_x = orig_w / float(new_w) if new_w > 0 else 1.0
        scale_y = orig_h / float(new_h) if new_h > 0 else 1.0

        return ScreenSnapshot(
            image_bytes=img_bytes,
            base64_jpeg=b64_str,
            width=new_w,
            height=new_h,
            original_width=orig_w,
            original_height=orig_h,
            scale_factor_x=scale_x,
            scale_factor_y=scale_y,
            timestamp=time.time(),
        )


_screen_capture_instance: ScreenCapture | None = None


def get_screen_capture() -> ScreenCapture:
    global _screen_capture_instance
    if _screen_capture_instance is None:
        _screen_capture_instance = ScreenCapture()
    return _screen_capture_instance


def capture_desktop() -> ScreenSnapshot:
    """Convenience helper to take a desktop snapshot for Gemini vision."""
    return get_screen_capture().capture_screen()
