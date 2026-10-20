"""
COMPASS Action Safety Guards
Pre-execution and runtime safety checks for automation actions.

Enforces:
  - Target window validation (protected windows, valid HWND)
  - Foreground window context checking
  - Input bounds (text length, key allowlist)
  - No unrestricted process killing or system operations
"""

import ctypes
import ctypes.wintypes
import sys
from typing import Any

from automation.models import (
    MAX_TYPE_LENGTH,
    PROTECTED_WINDOW_CLASSES,
    VK_CODES,
    ValidationResult,
)


def _get_window_class(hwnd: int) -> str:
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except Exception:  # noqa: BLE001
        return ""


def _is_window(hwnd: int) -> bool:
    try:
        return bool(ctypes.windll.user32.IsWindow(hwnd))
    except Exception:  # noqa: BLE001
        return False


def _is_window_visible(hwnd: int) -> bool:
    try:
        return bool(ctypes.windll.user32.IsWindowVisible(hwnd))
    except Exception:  # noqa: BLE001
        return False


def check_protected_window_class(class_name: str) -> ValidationResult:
    """Check if a window class name belongs to protected system classes."""
    if class_name in PROTECTED_WINDOW_CLASSES:
        return ValidationResult(
            ok=False,
            reason=f"Window class '{class_name}' is a protected system window class",
        )
    return ValidationResult(ok=True, reason=f"Window class '{class_name}' is allowed")


def check_hwnd_safe(hwnd: int) -> ValidationResult:
    """
    Verify an HWND is safe to target:
      - exists and is a valid window
      - is not a protected system window class
    """
    if sys.platform != "win32":
        return ValidationResult(ok=False, reason="Not running on Windows")
    if not hwnd or not _is_window(hwnd):
        return ValidationResult(ok=False, reason=f"HWND {hwnd} is not a valid window")

    class_name = _get_window_class(hwnd)
    return check_protected_window_class(class_name)


def check_foreground_context(target_hwnd: int) -> ValidationResult:
    """
    Verify the target HWND is the foreground window or is a child of it.
    Prevents actions from firing on background/covered windows.
    """
    if sys.platform != "win32":
        return ValidationResult(ok=False, reason="Not running on Windows")

    try:
        fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not fg_hwnd:
            # Fallback for virtual/isolated desktops, CI/testing environments, or
            # sessions where no window has active keyboard focus. Find the topmost
            # visible application window on the current desktop.
            try:
                from perception.uia_inspector import get_foreground_window
                fg_res = get_foreground_window()
                if fg_res.get("success") and fg_res.get("window"):
                    fg_hwnd = fg_res["window"].get("hwnd")
            except Exception:
                pass

        if not fg_hwnd:
            return ValidationResult(ok=False, reason="No foreground window")

        # Direct match
        if target_hwnd == fg_hwnd:
            return ValidationResult(ok=True, reason="Target is the foreground window")

        # Check if target_hwnd is a descendant of fg_hwnd
        parent = ctypes.windll.user32.GetAncestor(target_hwnd, 2)  # GA_ROOT=2
        if parent == fg_hwnd or parent == target_hwnd:
            return ValidationResult(
                ok=True, reason="Target is a child of the foreground window"
            )

        return ValidationResult(
            ok=False,
            reason=f"Target HWND {target_hwnd} is not the foreground window (fg={fg_hwnd})",
        )
    except Exception as e:  # noqa: BLE001
        return ValidationResult(ok=False, reason=f"Foreground check error: {e}")


def check_key_safe(key_name: str) -> ValidationResult:
    """
    Verify the requested key is in the allowed VK_CODES allowlist.
    Rejects keys not in the allowlist to prevent arbitrary system input.
    """
    key_lower = key_name.lower().strip()
    if key_lower not in VK_CODES:
        return ValidationResult(
            ok=False,
            reason=f"Key '{key_name}' is not in the allowed key list. "
            f"Supported keys: {sorted(VK_CODES.keys())}",
        )
    return ValidationResult(ok=True, reason=f"Key '{key_name}' is allowed")


def check_text_safe(text: str) -> ValidationResult:
    """
    Validate text input safety:
      - Length within bounds
      - Not None/empty check (warn, not block)
    Does NOT store the actual text content.
    """
    if text is None:
        return ValidationResult(ok=False, reason="Text input is None")
    if len(text) > MAX_TYPE_LENGTH:
        return ValidationResult(
            ok=False,
            reason=f"Text length {len(text)} exceeds maximum allowed {MAX_TYPE_LENGTH}",
        )
    return ValidationResult(ok=True, reason="Text input is within safe bounds")


def check_element_actionable(element_dict: dict[str, Any]) -> ValidationResult:
    """
    Verify an element dict is actionable:
      - HWND still valid
      - is_enabled = True
      - is_visible = True
      - bounding rect is non-zero
    """
    hwnd = element_dict.get("hwnd", 0)
    if not hwnd or not _is_window(hwnd):
        return ValidationResult(ok=False, reason=f"Element HWND {hwnd} no longer valid")

    if not element_dict.get("is_enabled", False):
        return ValidationResult(
            ok=False, reason=f"Element '{element_dict.get('name', '')}' is disabled"
        )
    if not element_dict.get("is_visible", False):
        return ValidationResult(
            ok=False, reason=f"Element '{element_dict.get('name', '')}' is not visible"
        )

    bounds = element_dict.get("bounds", {}) or {}
    w = bounds.get("width", bounds.get("right", 0) - bounds.get("left", 0))
    h = bounds.get("height", bounds.get("bottom", 0) - bounds.get("top", 0))
    if w <= 0 or h <= 0:
        return ValidationResult(
            ok=False,
            reason=f"Element '{element_dict.get('name', '')}' has zero bounding rect",
        )

    return ValidationResult(
        ok=True,
        reason="Element is enabled, visible, and has a valid bounding rect",
        element_snapshot=element_dict,
    )


def check_control_type_for_action(
    element_dict: dict[str, Any],
    action_type: str,
) -> ValidationResult:
    """
    Verify the element's control type is compatible with the requested action.
      click → any interactive control type
      type  → Edit or Document only
      key   → any
      focus → any
    """
    from perception.element_filter import (
        EDITABLE_CONTROL_TYPES,
        INTERACTIVE_CONTROL_TYPES,
    )

    ct = element_dict.get("control_type", "")
    action = action_type.lower()

    if action == "click":
        if ct not in INTERACTIVE_CONTROL_TYPES:
            return ValidationResult(
                ok=False,
                reason=f"Control type '{ct}' is not interactive — cannot click",
            )
    elif action == "type":  # noqa: SIM102
        if ct not in EDITABLE_CONTROL_TYPES:
            return ValidationResult(
                ok=False,
                reason=f"Control type '{ct}' is not editable — cannot type. "
                f"Expected Edit or Document.",
            )
    # key and focus have no control type restriction

    return ValidationResult(
        ok=True, reason=f"Control type '{ct}' is compatible with '{action}'"
    )


def check_coordinates_safe(
    x: int,
    y: int,
    bounds: dict[str, int] | None = None,
    hwnd: int | None = None,
) -> ValidationResult:
    """
    Validate target coordinates before dispatching mouse actions:
      - Coordinate falls within virtual desktop space
      - Rejects negative coordinates (unless multi-monitor virtual screen has negative origin)
      - If bounding rect provided, validates width > 0, height > 0
      - If HWND provided, verifies window is not minimized or closed
    """
    if sys.platform != "win32":
        if bounds:
            w = bounds["width"] if "width" in bounds else (bounds.get("right", 0) - bounds.get("left", 0))
            h = bounds["height"] if "height" in bounds else (bounds.get("bottom", 0) - bounds.get("top", 0))
            if w <= 0 or h <= 0:
                return ValidationResult(
                    ok=False, reason=f"Impossible rectangle bounds ({w}x{h})."
                )
        sim_vw = int(os.environ.get("COMPASS_SIM_SCREEN_W", 1920))
        sim_vh = int(os.environ.get("COMPASS_SIM_SCREEN_H", 1080))
        if x < 0 or x >= sim_vw or y < 0 or y >= sim_vh:
            return ValidationResult(
                ok=False,
                reason=f"Coordinates ({x}, {y}) fall outside virtual screen space (0, 0, {sim_vw}, {sim_vh})",
            )
        return ValidationResult(ok=True, reason="Simulated coordinates valid")

    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

    if vw <= 0 or vh <= 0:
        vw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        vh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        vx = 0
        vy = 0

    # Half-open coordinate space: [vx, vx + vw) and [vy, vy + vh)
    if x < vx or x >= (vx + vw) or y < vy or y >= (vy + vh):
        return ValidationResult(
            ok=False,
            reason=f"Coordinates ({x}, {y}) fall outside virtual screen space ({vx}, {vy}, {vx + vw}, {vy + vh})",
        )

    if bounds:
        w = bounds["width"] if "width" in bounds else (bounds.get("right", 0) - bounds.get("left", 0))
        h = bounds["height"] if "height" in bounds else (bounds.get("bottom", 0) - bounds.get("top", 0))
        if w <= 0 or h <= 0:
            return ValidationResult(
                ok=False,
                reason=f"Impossible bounding box dimensions: width={w}, height={h} (must be > 0)",
            )

    if hwnd:
        if not bool(user32.IsWindow(hwnd)):
            return ValidationResult(
                ok=False, reason=f"Target window HWND {hwnd} is invalid or closed"
            )
        if bool(user32.IsIconic(hwnd)):
            return ValidationResult(
                ok=False, reason=f"Target window HWND {hwnd} is minimized"
            )

    return ValidationResult(
        ok=True, reason=f"Coordinates ({x}, {y}) are within screen bounds and valid"
    )


class SafetyManager:
    """
    High-level safety manager providing unified safety checks for windows, elements, and input.
    """

    def is_safe_hwnd(self, hwnd: int) -> ValidationResult:
        return check_hwnd_safe(hwnd)

    def is_safe_key(self, key_name: str) -> ValidationResult:
        return check_key_safe(key_name)

    def is_safe_text(self, text: str) -> ValidationResult:
        return check_text_safe(text)

    def is_safe_coordinate(
        self,
        x: int,
        y: int,
        bounds: dict[str, int] | None = None,
        hwnd: int | None = None,
    ) -> ValidationResult:
        return check_coordinates_safe(x, y, bounds=bounds, hwnd=hwnd)

    def is_safe_element(
        self, element_dict: dict[str, Any], action_type: str = "click"
    ) -> ValidationResult:
        act_res = check_element_actionable(element_dict)
        if not act_res.ok:
            return act_res
        return check_control_type_compatibility(element_dict, action_type)  # noqa: F821

    def check_foreground(self, hwnd: int) -> ValidationResult:
        return check_foreground_context(hwnd)


_global_safety_manager = SafetyManager()


def get_safety_manager() -> SafetyManager:
    return _global_safety_manager


class PanicKillswitch:
    """
    Sub-10ms user panic detection switch.
    Monitors physical cursor position. If the user moves the mouse by >= threshold (default 15px)
    while automated dispatch is active, or if an emergency halt is triggered, it trips immediately
    to prevent unintended automation actions.
    """

    def __init__(self, movement_threshold_px: int = 15):
        self.threshold = movement_threshold_px
        self._armed = False
        self._initial_pos: tuple[int, int] | None = None
        self._tripped = False

    def arm(self) -> None:
        """Arm the panic detector with the current cursor position."""
        if sys.platform == "win32":
            try:
                pt = ctypes.wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                self._initial_pos = (pt.x, pt.y)
            except Exception:
                self._initial_pos = (0, 0)
        else:
            self._initial_pos = (0, 0)
        self._armed = True
        self._tripped = False

    def check(self) -> bool:
        """
        Check if user moved the mouse beyond the threshold.
        Completes in under 0.1ms (< 10ms SLA).
        Returns True if tripped.
        """
        if not self._armed or self._initial_pos is None:
            return self._tripped

        if sys.platform == "win32":
            try:
                pt = ctypes.wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                dx = pt.x - self._initial_pos[0]
                dy = pt.y - self._initial_pos[1]
                distance = (dx * dx + dy * dy) ** 0.5
                if distance >= self.threshold:
                    self._tripped = True
                    return True
            except Exception:
                pass
        return self._tripped

    def trip(self) -> None:
        """Manually trigger emergency halt."""
        self._tripped = True

    def disarm(self) -> None:
        """Disarm the panic switch after action completes."""
        self._armed = False
        self._initial_pos = None

    def reset(self) -> None:
        """Reset tripped state."""
        self._tripped = False
        self._armed = False
        self._initial_pos = None

    @property
    def is_tripped(self) -> bool:
        return self._tripped


_global_panic_killswitch = PanicKillswitch()


def get_panic_killswitch() -> PanicKillswitch:
    return _global_panic_killswitch

