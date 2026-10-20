"""
COMPASS Action Dispatcher
Safe, controlled UI action execution.

Execution priority for each action:
  CLICK:  UIA InvokePattern → fallback to SendInput at validated center point
  TYPE:   UIA ValuePattern::SetValue → fallback to SendInput char sequence
  KEY:    Win32 SendInput (key must be in VK_CODES allowlist)
  FOCUS:  UIA SetFocus

Fallback to coordinate-based SendInput is:
  - Only used when UIA pattern execution fails
  - Only after fresh element revalidation
  - Always recorded as "sendinput" in the audit log
  - Never exposed as a public API endpoint

NOTE: This module does NOT call validate_* directly — the caller (router) must
call ActionValidator first and pass the validated fresh element snapshot.
"""

import ctypes
import ctypes.wintypes
import os
import subprocess
import time
from typing import Any

from automation.action_log import log_action
from automation.models import VK_CODES, ActionResult, ExecutionMethod
from backend.app.logging_config import logger

# UIA Pattern IDs
UIA_INVOKE_PATTERN_ID = 10000
UIA_VALUE_PATTERN_ID = 10002

# Win32 SendInput structures (64-bit ABI compliant)
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _INPUT_UNION),
    ]


def _send_vk(vk_code: int) -> bool:
    """Send a virtual key press+release via SendInput."""
    try:
        inputs = (INPUT * 2)()

        inputs[0].type = INPUT_KEYBOARD
        inputs[0].union.ki.wVk = vk_code
        inputs[0].union.ki.dwFlags = 0
        inputs[0].union.ki.dwExtraInfo = 0

        inputs[1].type = INPUT_KEYBOARD
        inputs[1].union.ki.wVk = vk_code
        inputs[1].union.ki.dwFlags = KEYEVENTF_KEYUP
        inputs[1].union.ki.dwExtraInfo = 0

        sent = ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        return sent == 2
    except Exception:  # noqa: BLE001
        return False


def _send_unicode_char(char: str) -> bool:
    """Send a single unicode character via SendInput UNICODE event."""
    if char == "\n" or char == "\r":
        return _send_vk(0x0D)  # VK_RETURN
    if char == "\t":
        return _send_vk(0x09)  # VK_TAB
    try:
        inputs = (INPUT * 2)()
        scan_code = ord(char)

        inputs[0].type = INPUT_KEYBOARD
        inputs[0].union.ki.wVk = 0
        inputs[0].union.ki.wScan = scan_code
        inputs[0].union.ki.dwFlags = KEYEVENTF_UNICODE
        inputs[0].union.ki.dwExtraInfo = 0

        inputs[1].type = INPUT_KEYBOARD
        inputs[1].union.ki.wVk = 0
        inputs[1].union.ki.wScan = scan_code
        inputs[1].union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        inputs[1].union.ki.dwExtraInfo = 0

        sent = ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        return sent == 2
    except Exception:  # noqa: BLE001
        return False


def _get_uia_element(hwnd: int, runtime_id: str):
    """Attempt to get IUIAutomation element by HWND for pattern invocation."""
    try:
        import comtypes
        import comtypes.client

        try:
            comtypes.CoInitialize()
        except Exception:  # noqa: BLE001, S110
            pass
        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=comtypes.gen.UIAutomationClient.IUIAutomation,
        )
        return uia.ElementFromHandle(hwnd), uia
    except Exception:  # noqa: BLE001
        return None, None


def _find_uia_element_by_runtime_id(uia, hwnd: int, runtime_id: str):
    """Walk UIA tree to find element matching runtime_id."""
    try:
        root = uia.ElementFromHandle(hwnd)
        if root is None:
            return None

        target_id = runtime_id  # stored as str representation of list

        def _walk(el):
            try:
                rid = str(list(el.GetRuntimeId()))
                if rid == target_id:
                    return el
                child = uia.ControlViewWalker.GetFirstChildElement(el)
                while child is not None:
                    found = _walk(child)
                    if found is not None:
                        return found
                    child = uia.ControlViewWalker.GetNextSiblingElement(child)
            except Exception:  # noqa: BLE001, S110
                pass
            return None

        return _walk(root)
    except Exception:  # noqa: BLE001
        return None


def click_element(
    element_snapshot: dict[str, Any],
    task_id: str | None = None,
    timeout_sec: float = 5.0,
) -> ActionResult:
    """
    Click a UI element via UIA InvokePattern.
    Falls back to SendInput at center point only if UIA pattern fails.

    Args:
        element_snapshot: Validated, fresh element dict from ActionValidator.
        task_id:          Optional task context for audit logging.
        timeout_sec:      Per-action timeout.

    Returns:
        ActionResult
    """
    start = time.time()
    action = ActionResult(
        action_type="click",
        success=False,
        target_name=element_snapshot.get("name", ""),
        target_control_type=element_snapshot.get("control_type", ""),
    )
    hwnd = element_snapshot.get("hwnd", 0)
    runtime_id = element_snapshot.get("runtime_id", "")

    # Target window validation: ensure window exists and is not closed/stale
    user32 = ctypes.windll.user32
    if not hwnd or not bool(user32.IsWindow(hwnd)):
        action.error = (
            f"Target HWND {hwnd} is not a valid window (window closed or stale)"
        )
        action.duration_ms = round((time.time() - start) * 1000, 2)
        action.log_id = log_action(
            "click",
            element_snapshot,
            "rejected",
            False,
            error=action.error,
            task_id=task_id,
        )
        return action

    # Strategy 1: UIA InvokePattern
    try:
        import comtypes
        import comtypes.client
        import comtypes.gen.UIAutomationClient as UIA

        try:
            comtypes.CoInitialize()
        except Exception:  # noqa: BLE001, S110
            pass

        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=UIA.IUIAutomation,
        )
        el = _find_uia_element_by_runtime_id(uia, hwnd, runtime_id)
        if el is not None:
            try:
                pattern = el.GetCurrentPattern(UIA_INVOKE_PATTERN_ID)
                if pattern:
                    invoke = pattern.QueryInterface(UIA.IUIAutomationInvokePattern)
                    invoke.Invoke()
                    action.success = True
                    action.execution_method = ExecutionMethod.UIA_INVOKE.value
                    action.duration_ms = round((time.time() - start) * 1000, 2)
                    action.log_id = log_action(
                        "click",
                        element_snapshot,
                        action.execution_method,
                        True,
                        task_id=task_id,
                    )
                    return action
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    f"UIA InvokePattern failed for '{action.target_name}': {e}"
                )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"UIA click setup failed: {e}")

    # Ensure target window is restored and active
    if hwnd and bool(user32.IsWindow(hwnd)):
        try:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.AllowSetForegroundWindow(0xFFFFFFFF)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    # Strategy 2: SendInput at center point (validated fallback only)
    if time.time() - start < timeout_sec:
        try:
            bounds = element_snapshot.get("bounds", {})
            cx = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
            cy = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2

            if cx > 0 or cy > 0:
                user32 = ctypes.windll.user32
                MOUSEEVENTF_LEFTDOWN = 0x0002
                MOUSEEVENTF_LEFTUP = 0x0004

                user32.SetCursorPos(cx, cy)
                time.sleep(0.03)
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.02)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                action.success = True
                action.execution_method = ExecutionMethod.SENDINPUT.value
                action.duration_ms = round((time.time() - start) * 1000, 2)
                logger.info(
                    f"Click executed via SendInput fallback on '{action.target_name}' at ({cx},{cy})"
                )
                action.log_id = log_action(
                    "click",
                    element_snapshot,
                    action.execution_method,
                    True,
                    task_id=task_id,
                    parameters_meta={
                        "fallback": True,
                        "center_x": cx,
                        "center_y": cy,
                    },
                )
                return action
        except Exception as e:  # noqa: BLE001
            action.error = str(e)

    action.error = action.error or "All click strategies failed (if target is running as Administrator, run COMPASS as Administrator)"
    action.duration_ms = round((time.time() - start) * 1000, 2)
    log_action(
        "click", element_snapshot, "failed", False, error=action.error, task_id=task_id
    )
    return action


def type_text(
    element_snapshot: Any,
    text: str | None = None,
    task_id: str | None = None,
    timeout_sec: float = 10.0,
) -> ActionResult:
    """
    Type text into an editable element via UIA ValuePattern::SetValue.
    Falls back to SendInput unicode sequence only if ValuePattern fails.

    Privacy: text_length is logged, NOT the actual text content.
    """
    if isinstance(element_snapshot, str) and text is None:
        text = element_snapshot
        user32 = ctypes.windll.user32
        fg = user32.GetForegroundWindow()
        element_snapshot = {
            "hwnd": fg,
            "name": "focused",
            "control_type": "Edit",
            "runtime_id": "",
        }
    elif not isinstance(element_snapshot, dict):
        element_snapshot = {}
    if text is None:
        text = ""

    start = time.time()
    action = ActionResult(
        action_type="type",
        success=False,
        target_name=element_snapshot.get("name", ""),
        target_control_type=element_snapshot.get("control_type", ""),
    )

    hwnd = element_snapshot.get("hwnd", 0)
    runtime_id = element_snapshot.get("runtime_id", "")
    text_length = len(text)
    # Never log the actual text — only metadata
    meta = {"text_length": text_length}

    # Target window validation
    user32 = ctypes.windll.user32
    window_valid = bool(hwnd) and bool(user32.IsWindow(hwnd))

    if not window_valid:
        if element_snapshot.get("name") == "focused":
            # Global typing fallback without specific window
            logger.warning(
                f"Target HWND {hwnd} invalid for global type; falling back to SendInput directly."
            )
        else:
            action.error = (
                f"Target HWND {hwnd} is not a valid window (window closed or stale)"
            )
            action.duration_ms = round((time.time() - start) * 1000, 2)
            action.log_id = log_action(
                "type",
                element_snapshot,
                "rejected",
                False,
                error=action.error,
                task_id=task_id,
                parameters_meta=meta,
            )
            return action

    # Strategy 1: UIA ValuePattern::SetValue (only if window is valid)
    if window_valid:
        try:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.AllowSetForegroundWindow(0xFFFFFFFF)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        try:
            import comtypes
            import comtypes.client
            import comtypes.gen.UIAutomationClient as UIA

            try:
                comtypes.CoInitialize()
            except Exception:  # noqa: BLE001, S110
                pass

            uia = comtypes.client.CreateObject(
                "{ff48dba4-60ef-4201-aa87-54103eef594e}",
                interface=UIA.IUIAutomation,
            )
            el = _find_uia_element_by_runtime_id(uia, hwnd, runtime_id)
            if el is not None:
                try:
                    pattern = el.GetCurrentPattern(UIA_VALUE_PATTERN_ID)
                    if pattern:
                        vp = pattern.QueryInterface(UIA.IUIAutomationValuePattern)
                        if not vp.CurrentIsReadOnly:
                            vp.SetValue(text)
                            action.success = True
                            action.execution_method = ExecutionMethod.UIA_VALUE.value
                            action.duration_ms = round((time.time() - start) * 1000, 2)
                            action.log_id = log_action(
                                "type",
                                element_snapshot,
                                action.execution_method,
                                True,
                                task_id=task_id,
                                parameters_meta=meta,
                            )
                            return action
                except Exception as e:  # noqa: BLE001
                    logger.debug(
                        f"UIA ValuePattern failed for '{action.target_name}': {e}"
                    )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"UIA type setup failed: {e}")

    # Strategy 2: SendInput unicode sequence (validated fallback)
    if time.time() - start < timeout_sec:
        try:
            # Focus the element first
            try:
                import comtypes.client
                import comtypes.gen.UIAutomationClient as UIA2

                uia2 = comtypes.client.CreateObject(
                    "{ff48dba4-60ef-4201-aa87-54103eef594e}",
                    interface=UIA2.IUIAutomation,
                )
                el2 = _find_uia_element_by_runtime_id(uia2, hwnd, runtime_id)
                if el2:
                    el2.SetFocus()
                    time.sleep(0.05)
            except Exception:  # noqa: BLE001, S110
                pass

            success_count = 0
            for char in text:
                if time.time() - start > timeout_sec:
                    break
                if _send_unicode_char(char):
                    success_count += 1
                time.sleep(0.005)  # 5ms between chars for stability

            action.success = success_count == text_length
            action.execution_method = ExecutionMethod.SENDINPUT.value
            action.duration_ms = round((time.time() - start) * 1000, 2)
            action.log_id = log_action(
                "type",
                element_snapshot,
                action.execution_method,
                action.success,
                task_id=task_id,
                parameters_meta={**meta, "fallback": True, "chars_sent": success_count},
            )
            return action
        except Exception as e:  # noqa: BLE001
            action.error = str(e)

    action.error = action.error or "All type strategies failed (if target is running as Administrator, run COMPASS as Administrator)"
    action.duration_ms = round((time.time() - start) * 1000, 2)
    log_action(
        "type",
        element_snapshot,
        "failed",
        False,
        error=action.error,
        task_id=task_id,
        parameters_meta=meta,
    )
    return action


def send_key(
    key_name: str,
    task_id: str | None = None,
) -> ActionResult:
    """
    Send a validated keyboard key via SendInput.
    key_name must be in VK_CODES allowlist (enforced by ActionValidator before calling this).
    """
    start = time.time()
    vk_code = VK_CODES.get(key_name.lower())
    action = ActionResult(
        action_type="key",
        success=False,
        target_name=f"key:{key_name}",
        execution_method=ExecutionMethod.SENDINPUT.value,
    )

    if vk_code is None:
        action.error = f"Key '{key_name}' not in allowed key list"
        return action

    try:
        ok = _send_vk(vk_code)
        action.success = ok
        action.error = None if ok else "SendInput returned failure"
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action(
            "key",
            None,
            ExecutionMethod.SENDINPUT.value,
            ok,
            task_id=task_id,
            parameters_meta={"key": key_name, "vk_code": vk_code},
        )
    except Exception as e:  # noqa: BLE001
        action.error = str(e)
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action("key", None, "failed", False, error=str(e), task_id=task_id)

    return action


def focus_element(
    element_snapshot: dict[str, Any],
    task_id: str | None = None,
) -> ActionResult:
    """
    Set focus on a UI element via UIA SetFocus.
    """
    start = time.time()
    action = ActionResult(
        action_type="focus",
        success=False,
        target_name=element_snapshot.get("name", ""),
        target_control_type=element_snapshot.get("control_type", ""),
        execution_method=ExecutionMethod.UIA_FOCUS.value,
    )

    hwnd = element_snapshot.get("hwnd", 0)
    runtime_id = element_snapshot.get("runtime_id", "")

    # Target window validation: ensure window exists and is not closed/stale
    user32 = ctypes.windll.user32
    if not hwnd or not bool(user32.IsWindow(hwnd)):
        action.error = (
            f"Target HWND {hwnd} is not a valid window (window closed or stale)"
        )
        action.duration_ms = round((time.time() - start) * 1000, 2)
        action.log_id = log_action(
            "focus",
            element_snapshot,
            "rejected",
            False,
            error=action.error,
            task_id=task_id,
        )
        return action

    try:
        import comtypes
        import comtypes.client
        import comtypes.gen.UIAutomationClient as UIA

        try:
            comtypes.CoInitialize()
        except Exception:  # noqa: BLE001, S110
            pass

        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=UIA.IUIAutomation,
        )
        el = _find_uia_element_by_runtime_id(uia, hwnd, runtime_id)
        if el is not None:
            el.SetFocus()
            action.success = True
            action.duration_ms = round((time.time() - start) * 1000, 2)
            log_action(
                "focus",
                element_snapshot,
                action.execution_method,
                True,
                task_id=task_id,
            )
            return action
        else:
            action.error = "Element not found via UIA for focus"
    except Exception as e:  # noqa: BLE001
        action.error = str(e)

    # Strategy 2: If UIA SetFocus failed or element is window, bring window to foreground
    if hwnd and bool(user32.IsWindow(hwnd)):
        try:
            user32.AllowSetForegroundWindow(0xFFFFFFFF)
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            action.success = True
            action.duration_ms = round((time.time() - start) * 1000, 2)
            log_action(
                "focus",
                element_snapshot,
                action.execution_method,
                True,
                task_id=task_id,
            )
            return action
        except Exception as e:  # noqa: BLE001
            action.error = str(e)

    action.duration_ms = round((time.time() - start) * 1000, 2)
    log_action(
        "focus", element_snapshot, "failed", False, error=action.error, task_id=task_id
    )
    return action


def double_click_element(
    element_snapshot: dict[str, Any],
    task_id: str | None = None,
    timeout_sec: float = 3.0,
) -> ActionResult:
    """
    Perform a double-click on a target UI element.
    """
    start = time.time()
    action = ActionResult(
        action_type="double_click",
        success=False,
        target_name=element_snapshot.get("name", ""),
        target_control_type=element_snapshot.get("control_type", ""),
        execution_method=ExecutionMethod.SENDINPUT.value,
    )

    try:
        bounds = element_snapshot.get("bounds", {})
        cx = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
        cy = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2

        if cx > 0 or cy > 0:
            user32 = ctypes.windll.user32
            MOUSEEVENTF_LEFTDOWN = 0x0002
            MOUSEEVENTF_LEFTUP = 0x0004
            MOUSEEVENTF_ABSOLUTE = 0x8000

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            if screen_w > 0 and screen_h > 0:
                nx = int(cx * 65535 / screen_w)
                ny = int(cy * 65535 / screen_h)

                user32.SetCursorPos(cx, cy)
                time.sleep(0.04)
                # First click
                user32.mouse_event(
                    MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0
                )
                time.sleep(0.02)
                user32.mouse_event(
                    MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0
                )
                # Second click
                time.sleep(0.05)
                user32.mouse_event(
                    MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0
                )
                time.sleep(0.02)
                user32.mouse_event(
                    MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0
                )

                action.success = True
                action.duration_ms = round((time.time() - start) * 1000, 2)
                log_action(
                    "double_click",
                    element_snapshot,
                    action.execution_method,
                    True,
                    task_id=task_id,
                )
                return action
    except Exception as e:  # noqa: BLE001
        action.error = str(e)

    action.error = action.error or "Double click failed"
    action.duration_ms = round((time.time() - start) * 1000, 2)
    log_action(
        "double_click",
        element_snapshot,
        "failed",
        False,
        error=action.error,
        task_id=task_id,
    )
    return action


def right_click_element(
    element_snapshot: dict[str, Any],
    task_id: str | None = None,
) -> ActionResult:
    """
    Perform a right-click on a target UI element to open its context menu.
    """
    start = time.time()
    action = ActionResult(
        action_type="right_click",
        success=False,
        target_name=element_snapshot.get("name", ""),
        target_control_type=element_snapshot.get("control_type", ""),
        execution_method=ExecutionMethod.SENDINPUT.value,
    )

    try:
        bounds = element_snapshot.get("bounds", {})
        cx = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
        cy = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2

        if cx > 0 or cy > 0:
            user32 = ctypes.windll.user32
            MOUSEEVENTF_RIGHTDOWN = 0x0008
            MOUSEEVENTF_RIGHTUP = 0x0010
            MOUSEEVENTF_ABSOLUTE = 0x8000

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            if screen_w > 0 and screen_h > 0:
                nx = int(cx * 65535 / screen_w)
                ny = int(cy * 65535 / screen_h)

                user32.SetCursorPos(cx, cy)
                time.sleep(0.04)
                user32.mouse_event(
                    MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0
                )
                time.sleep(0.03)
                user32.mouse_event(
                    MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0
                )

                action.success = True
                action.duration_ms = round((time.time() - start) * 1000, 2)
                log_action(
                    "right_click",
                    element_snapshot,
                    action.execution_method,
                    True,
                    task_id=task_id,
                )
                return action
    except Exception as e:  # noqa: BLE001
        action.error = str(e)

    action.error = action.error or "Right click failed"
    action.duration_ms = round((time.time() - start) * 1000, 2)
    log_action(
        "right_click",
        element_snapshot,
        "failed",
        False,
        error=action.error,
        task_id=task_id,
    )
    return action


def move_cursor(
    x: int,
    y: int,
    task_id: str | None = None,
) -> ActionResult:
    """
    Move the mouse cursor to the specified screen coordinates.
    """
    start = time.time()
    action = ActionResult(
        action_type="move",
        success=False,
        target_name=f"coord:({x},{y})",
        execution_method=ExecutionMethod.SENDINPUT.value,
    )

    try:
        user32 = ctypes.windll.user32
        ok = bool(user32.SetCursorPos(x, y))
        action.success = ok
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action(
            "move",
            None,
            action.execution_method,
            ok,
            task_id=task_id,
            parameters_meta={"x": x, "y": y},
        )
        return action
    except Exception as e:  # noqa: BLE001
        action.error = str(e)
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action("move", None, "failed", False, error=str(e), task_id=task_id)
        return action


def scroll_element(
    element_snapshot: dict[str, Any],
    delta: int = -120,
    task_id: str | None = None,
) -> ActionResult:
    """
    Scroll mouse wheel at element position. Positive delta = scroll up, negative delta = scroll down.
    """
    start = time.time()
    action = ActionResult(
        action_type="scroll",
        success=False,
        target_name=element_snapshot.get("name", ""),
        execution_method=ExecutionMethod.SENDINPUT.value,
    )

    try:
        bounds = element_snapshot.get("bounds", {})
        cx = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
        cy = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2

        user32 = ctypes.windll.user32
        MOUSEEVENTF_WHEEL = 0x0800
        if cx > 0 and cy > 0:
            user32.SetCursorPos(cx, cy)
            time.sleep(0.02)

        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        action.success = True
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action(
            "scroll",
            element_snapshot,
            action.execution_method,
            True,
            task_id=task_id,
            parameters_meta={"delta": delta},
        )
        return action
    except Exception as e:  # noqa: BLE001
        action.error = str(e)
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action(
            "scroll", element_snapshot, "failed", False, error=str(e), task_id=task_id
        )
        return action


def send_key_combination(
    combination: str,
    task_id: str | None = None,
) -> ActionResult:
    """
    Send a modifier key combination (e.g. 'ctrl+s', 'alt+f4', 'ctrl+shift+n').
    """
    start = time.time()
    action = ActionResult(
        action_type="key_combination",
        success=False,
        target_name=f"combo:{combination}",
        execution_method=ExecutionMethod.SENDINPUT.value,
    )

    keys = [k.strip().lower() for k in combination.replace("+", " ").split()]
    vk_list = []
    for k in keys:
        vk = VK_CODES.get(k)
        if vk is None:
            action.error = (
                f"Key '{k}' in combination '{combination}' is not allowlisted."
            )
            return action
        vk_list.append(vk)

    try:
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002

        # Press modifiers / keys down in sequence
        for vk in vk_list:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)

        time.sleep(0.03)

        # Release in reverse sequence
        for vk in reversed(vk_list):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)

        action.success = True
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action(
            "key_combination",
            None,
            action.execution_method,
            True,
            task_id=task_id,
            parameters_meta={"combination": combination},
        )
        return action
    except Exception as e:  # noqa: BLE001
        action.error = str(e)
        action.duration_ms = round((time.time() - start) * 1000, 2)
        log_action(
            "key_combination", None, "failed", False, error=str(e), task_id=task_id
        )
        return action


def highlight_element(
    element_snapshot: dict[str, Any],
    duration_ms: int = 1000,
    task_id: str | None = None,
) -> ActionResult:
    """
    Highlight an element bounds (non-destructive visual guidance via overlay IPC).
    """
    start = time.time()
    ipc_success = False
    ipc_error = None

    # Send IPC highlight request to Overlay window if active
    try:
        import json
        import urllib.request

        payload = json.dumps(
            {"elements": [element_snapshot], "duration_ms": duration_ms}
        ).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8001/highlight",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=0.15) as resp:  # nosec B310
            if resp.status in (200, 204):
                ipc_success = True
            else:
                ipc_error = f"Overlay IPC returned HTTP status {resp.status}"
    except Exception as e:  # noqa: BLE001
        # Overlay process is down or unreachable
        ipc_error = f"Overlay IPC unavailable or failed: {e}"

    action = ActionResult(
        action_type="highlight",
        success=ipc_success,
        error=ipc_error,
        target_name=element_snapshot.get("name", ""),
        target_control_type=element_snapshot.get("control_type", ""),
        execution_method="overlay_highlight",
    )
    action.duration_ms = round((time.time() - start) * 1000, 2)
    log_action(
        "highlight",
        element_snapshot,
        "overlay_highlight",
        ipc_success,
        error=ipc_error,
        task_id=task_id,
        parameters_meta={"duration_ms": duration_ms},
    )
    return action


# Aliases for compatibility
def dispatch_click(
    element_snapshot: dict[str, Any] | None = None,
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return click_element(target, task_id=task_id, **kwargs)


def dispatch_type(
    element_snapshot: dict[str, Any] | None = None,
    text: str = "",
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return type_text(target, text, task_id=task_id, **kwargs)


def dispatch_focus(
    element_snapshot: dict[str, Any] | None = None,
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return focus_element(target, task_id=task_id, **kwargs)


def dispatch_double_click(
    element_snapshot: dict[str, Any] | None = None,
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return double_click_element(target, task_id=task_id, **kwargs)


def dispatch_right_click(
    element_snapshot: dict[str, Any] | None = None,
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return right_click_element(target, task_id=task_id, **kwargs)


def dispatch_scroll(
    element_snapshot: dict[str, Any] | None = None,
    delta: int = -120,
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return scroll_element(target, delta=delta, task_id=task_id, **kwargs)


def dispatch_key_combination(
    combination: str, task_id: str | None = None, **kwargs
) -> ActionResult:
    return send_key_combination(combination, task_id=task_id, **kwargs)


def dispatch_highlight(
    element_snapshot: dict[str, Any] | None = None,
    duration_ms: int = 1000,
    task_id: str | None = None,
    element: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    target = element_snapshot if element_snapshot is not None else element
    return highlight_element(target, duration_ms=duration_ms, task_id=task_id, **kwargs)


def launch_application(
    app_name: str,
    path: str | None = None,
    args: list[str] | None = None,
    task_id: str | None = None,
    timeout_sec: float = 10.0,
) -> ActionResult:
    """
    Launch a local application or Windows URI protocol.
    Resolves executable path dynamically via AppDiscovery if not specified.
    """
    start = time.time()
    action = ActionResult(
        action_type="launch_app",
        success=False,
        target_name=app_name,
        target_control_type="Application",
    )

    from automation.app_discovery import get_app_discovery

    discovery = get_app_discovery()
    app_info = None

    if not path:
        app_info = discovery.discover_app(app_name)
        if app_info:
            path = app_info.path

    if not path and not (app_info and app_info.is_uri):
        action.error = f"Application '{app_name}' not found on this system"
        action.duration_ms = round((time.time() - start) * 1000, 2)
        action.log_id = log_action(
            "launch_app",
            {"name": app_name},
            "rejected",
            False,
            error=action.error,
            task_id=task_id,
        )
        return action

    # Clean corrupted Notepad state files if launching Notepad on Windows 11
    if "notepad" in app_name.lower():
        try:
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            if local_appdata:
                ws_dir = os.path.join(
                    local_appdata,
                    "Packages",
                    "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
                    "LocalState",
                    "WindowState",
                )
                if os.path.isdir(ws_dir):
                    entries = os.listdir(ws_dir)
                    if len(entries) > 20:
                        for f in entries:
                            fp = os.path.join(ws_dir, f)
                            try:
                                if os.path.isfile(fp):
                                    os.remove(fp)
                            except Exception:
                                pass
        except Exception:
            pass

    # 1. URI protocol launch (e.g. ms-settings:, calculator:, spotify:)
    if app_info and app_info.is_uri and app_info.uri:
        try:
            os.startfile(app_info.uri)  # type: ignore[attr-defined]
            action.success = True
            action.execution_method = ExecutionMethod.SHELL_EXECUTE.value
            action.duration_ms = round((time.time() - start) * 1000, 2)
            action.log_id = log_action(
                "launch_app",
                {"name": app_name, "uri": app_info.uri},
                action.execution_method,
                True,
                task_id=task_id,
            )
            return action
        except Exception as e:
            action.error = f"ShellExecute URI error for '{app_name}': {e}"

    # 2. Executable spawn
    if path:
        # Prefer os.startfile on Windows for GUI desktop applications without extra CLI arguments
        if os.name == "nt" and not args:
            try:
                os.startfile(path)  # type: ignore[attr-defined]
                action.success = True
                action.execution_method = ExecutionMethod.SHELL_EXECUTE.value
                action.duration_ms = round((time.time() - start) * 1000, 2)
                action.log_id = log_action(
                    "launch_app",
                    {"name": app_name, "path": path},
                    action.execution_method,
                    True,
                    task_id=task_id,
                )
                return action
            except Exception as sf_err:
                logger.debug(f"startfile attempt failed: {sf_err}, trying subprocess...")

        try:
            cmd = [path]
            if args:
                cmd.extend(args)

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.lpDesktop = r"WinSta0\Default"

            proc = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                close_fds=True,
            )
            action.success = True
            action.execution_method = ExecutionMethod.SUBPROCESS.value
            action.duration_ms = round((time.time() - start) * 1000, 2)
            action.log_id = log_action(
                "launch_app",
                {"name": app_name, "path": path, "pid": proc.pid},
                action.execution_method,
                True,
                task_id=task_id,
            )
            return action
        except Exception as e:
            # Fall back to os.startfile for Windows shell association (e.g. .lnk or Store apps)
            try:
                os.startfile(path)  # type: ignore[attr-defined]
                action.success = True
                action.execution_method = ExecutionMethod.SHELL_EXECUTE.value
                action.duration_ms = round((time.time() - start) * 1000, 2)
                action.log_id = log_action(
                    "launch_app",
                    {"name": app_name, "path": path, "fallback": "startfile"},
                    action.execution_method,
                    True,
                    task_id=task_id,
                )
                return action
            except Exception as ex2:
                action.error = f"Process spawn failed: {e}; Startfile failed: {ex2}"

    action.duration_ms = round((time.time() - start) * 1000, 2)
    action.log_id = log_action(
        "launch_app",
        {"name": app_name},
        "failed",
        False,
        error=action.error,
        task_id=task_id,
    )
    return action


def open_url(
    url: str,
    browser: str | None = None,
    task_id: str | None = None,
) -> ActionResult:
    """
    Open a web URL in the default browser or a specific browser.
    """
    start = time.time()
    action = ActionResult(
        action_type="open_url",
        success=False,
        target_name=url,
        target_control_type="Hyperlink",
    )

    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://") or clean_url.startswith("file://")):
        clean_url = "https://" + clean_url

    if browser:
        from automation.app_discovery import get_app_discovery
        browser_info = get_app_discovery().discover_app(browser)
        if browser_info and browser_info.path:
            try:
                subprocess.Popen([browser_info.path, clean_url])
                action.success = True
                action.execution_method = ExecutionMethod.SUBPROCESS.value
                action.duration_ms = round((time.time() - start) * 1000, 2)
                action.log_id = log_action(
                    "open_url",
                    {"url": clean_url, "browser": browser},
                    action.execution_method,
                    True,
                    task_id=task_id,
                )
                return action
            except Exception as e:
                logger.warning(f"Failed to launch specific browser {browser}: {e}")

    # Default browser via OS
    try:
        os.startfile(clean_url)  # type: ignore[attr-defined]
        action.success = True
        action.execution_method = ExecutionMethod.SHELL_EXECUTE.value
        action.duration_ms = round((time.time() - start) * 1000, 2)
        action.log_id = log_action(
            "open_url",
            {"url": clean_url},
            action.execution_method,
            True,
            task_id=task_id,
        )
        return action
    except Exception as e:
        action.error = f"Failed to open URL '{clean_url}': {e}"
        action.duration_ms = round((time.time() - start) * 1000, 2)
        action.log_id = log_action(
            "open_url",
            {"url": clean_url},
            "failed",
            False,
            error=action.error,
            task_id=task_id,
        )
        return action


def dispatch_launch_app(
    app_name: str = "",
    path: str | None = None,
    args: list[str] | None = None,
    task_id: str | None = None,
    **kwargs,
) -> ActionResult:
    return launch_application(app_name=app_name, path=path, args=args, task_id=task_id, **kwargs)


def dispatch_open_url(
    url: str = "",
    browser: str | None = None,
    task_id: str | None = None,
    **kwargs,
) -> ActionResult:
    return open_url(url=url, browser=browser, task_id=task_id, **kwargs)
