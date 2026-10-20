"""
COMPASS UIA Inspector
Windows UI Automation element discovery via comtypes COM interface.

Provides:
  get_foreground_window()          -> WindowInfo
  get_element_tree(hwnd, depth=3)  -> List[UIElement]
  find_element_by_name(hwnd, name) -> Optional[UIElement]
  find_element_by_type(hwnd, type) -> List[UIElement]

Graceful degradation: returns structured failure dict on COM/UIA init errors.
Never crashes the backend on UIA failures.
"""

import ctypes
import ctypes.wintypes
import sys
import threading
import time
from typing import Any

from perception.models import BoundingRect, UIElement, WindowInfo

# ─── UIA Control Type ID → Name mapping ──────────────────────────────────────
UIA_CONTROL_TYPES: dict[int, str] = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50027: "Thumb",
    50028: "DataGrid",
    50029: "DataItem",
    50030: "Document",
    50031: "SplitButton",
    50032: "Window",
    50033: "Pane",
    50034: "Header",
    50035: "HeaderItem",
    50036: "Table",
    50037: "TitleBar",
    50038: "Separator",
    50039: "SemanticZoom",
    50040: "AppBar",
}

# UIA Pattern IDs
UIA_INVOKE_PATTERN_ID = 10000
UIA_VALUE_PATTERN_ID = 10002
UIA_SCROLL_PATTERN_ID = 10004
UIA_EXPAND_COLLAPSE_PATTERN_ID = 10005
UIA_SELECTION_ITEM_PATTERN_ID = 10010
UIA_TEXT_PATTERN_ID = 10014
UIA_TOGGLE_PATTERN_ID = 10015

# Optimized Control Type Pattern Filtering (avoids unnecessary out-of-process COM roundtrips)
NON_INTERACTIVE_CONTROL_TYPES = {
    "Separator",
    "HeaderItem",
    "TitleBar",
    "ToolTip",
    "StatusBar",
    "Thumb",
}
INVOKE_CAPABLE_TYPES = {
    "Button",
    "Hyperlink",
    "MenuItem",
    "SplitButton",
    "ListItem",
    "Custom",
}
VALUE_TEXT_CAPABLE_TYPES = {
    "Edit",
    "Document",
    "ComboBox",
    "Spinner",
    "ProgressBar",
    "Slider",
    "Text",
    "Custom",
}
TOGGLE_CAPABLE_TYPES = {"CheckBox", "RadioButton", "MenuItem", "Button", "Custom"}
SELECTION_EXPAND_CAPABLE_TYPES = {
    "ListItem",
    "TabItem",
    "TreeItem",
    "RadioButton",
    "DataItem",
    "ComboBox",
    "Custom",
}
SCROLL_CAPABLE_TYPES = {
    "ScrollBar",
    "List",
    "Tree",
    "DataGrid",
    "Document",
    "Pane",
    "Window",
    "Custom",
}

# ─── COM UIA initialization ───────────────────────────────────────────────────
_uia_lock = threading.Lock()
_uia = None  # IUIAutomation COM object
_uia_available = None  # None = not tested; True/False = result
_uia_error = ""


def ensure_interactive_desktop() -> None:
    """Ensure the calling thread is attached to the interactive user desktop (WinSta0\\Default)."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        dt = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
        buf = ctypes.create_unicode_buffer(256)
        needed = ctypes.wintypes.DWORD(0)
        user32.GetUserObjectInformationW(dt, 2, buf, 512, ctypes.byref(needed))
        if "default" not in buf.value.lower():
            GENERIC_ALL = 0x10000000
            h_def = user32.OpenInputDesktop(0, False, GENERIC_ALL)
            if not h_def:
                h_def = user32.OpenDesktopW("Default", 0, False, GENERIC_ALL)
            if h_def:
                user32.SetThreadDesktop(h_def)
    except Exception:
        pass


def _init_uia() -> tuple[bool, str]:
    """Test UIA COM availability. Thread-safe. Called once."""
    global _uia_available, _uia_error
    ensure_interactive_desktop()
    with _uia_lock:
        if _uia_available is not None:
            return _uia_available, _uia_error
        if sys.platform != "win32":
            _uia_available = False
            _uia_error = "Not running on Windows"
            return False, _uia_error
        try:
            import comtypes
            import comtypes.client

            comtypes.CoInitialize()
            # Generate type library if not present
            try:
                comtypes.client.GetModule(
                    ("{944DE083-8FB8-45CF-BCB7-C477ACB2F897}", 1, 0)
                )
            except Exception:  # noqa: BLE001, S110
                pass
            # Verify we can import the generated module
            import comtypes.gen.UIAutomationClient

            _uia_available = True
            _uia_error = ""
            return True, ""
        except ImportError as e:
            _uia_available = False
            _uia_error = f"comtypes not installed: {e}"
            return False, _uia_error
        except Exception as e:  # noqa: BLE001
            _uia_available = False
            _uia_error = f"UIA COM init failed: {e}"
            return False, _uia_error


def _get_uia():
    """Return IUIAutomation COM object, initializing if needed. Returns None on failure."""
    ok, _ = _init_uia()
    if not ok:
        return None
    try:
        import comtypes
        import comtypes.client

        ensure_interactive_desktop()
        # Reinitialize COM on calling thread (required for MTA/STA compatibility)
        try:
            comtypes.CoInitialize()
        except Exception:  # noqa: BLE001, S110
            pass
        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=comtypes.gen.UIAutomationClient.IUIAutomation,
        )
        return uia
    except Exception:  # noqa: BLE001
        return None


def get_uia_status() -> dict[str, Any]:
    """Return current UIA subsystem status."""
    ok, err = _init_uia()
    return {
        "available": ok,
        "error": err if not ok else None,
        "platform": sys.platform,
    }


# ─── Win32 helper functions ───────────────────────────────────────────────────
def _get_hwnd_rect(hwnd: int) -> BoundingRect:
    """Get window bounding rectangle via GetWindowRect."""
    try:
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return BoundingRect(
                left=rect.left, top=rect.top, right=rect.right, bottom=rect.bottom
            )
    except Exception:  # noqa: BLE001, S110
        pass
    return BoundingRect()


def _get_window_class(hwnd: int) -> str:
    """Get Win32 class name of a window."""
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except Exception:  # noqa: BLE001
        return ""


def _get_window_title(hwnd: int) -> str:
    """Get window title text."""
    try:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
        return buf.value
    except Exception:  # noqa: BLE001
        return ""


def _get_window_pid(hwnd: int) -> int:
    """Get process ID owning hwnd."""
    try:
        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value
    except Exception:  # noqa: BLE001
        return 0


def _is_window(hwnd: int) -> bool:
    """Check if hwnd is a valid window."""
    try:
        return bool(ctypes.windll.user32.IsWindow(hwnd))
    except Exception:  # noqa: BLE001
        return False


def _is_window_minimized(hwnd: int) -> bool:
    try:
        return bool(ctypes.windll.user32.IsIconic(hwnd))
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
            ctypes.wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_CLOAKED),
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )
        if hr == 0 and cloaked.value != 0:
            return False
        rect = ctypes.wintypes.RECT()
        if not user32.GetWindowRect(ctypes.wintypes.HWND(hwnd), ctypes.byref(rect)):
            return False
        return (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0
    except Exception:
        return False


# ─── Public API ───────────────────────────────────────────────────────────────
def get_foreground_window() -> dict[str, Any]:
    """
    Return metadata for the current foreground window.
    Uses Win32 GetForegroundWindow + optional UIA for class/title.

    Returns:
        Dict with 'success', 'window' (WindowInfo dict), and optional 'error'.
    """
    try:
        ensure_interactive_desktop()
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd or not is_real_visible_desktop_window(hwnd):
            # Fallback for virtual/isolated desktops, CI/testing environments, or
            # sessions where no window has active keyboard focus. Find the topmost
            # visible application window on the current interactive desktop.
            top_candidate = None
            def fallback_cb(h, _):
                nonlocal top_candidate
                if is_real_visible_desktop_window(h) and not _is_window_minimized(h):
                    length = ctypes.windll.user32.GetWindowTextLengthW(h)
                    if length > 0:
                        cls = _get_window_class(h)
                        if cls not in (
                            "Progman",
                            "Shell_TrayWnd",
                            "Touch Tooltip Window",
                        ):
                            top_candidate = h
                            return False
                return True
            try:
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                h_def = ctypes.windll.user32.OpenInputDesktop(0, False, 0x10000000) or ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x10000000)
                if h_def:
                    ctypes.windll.user32.EnumDesktopWindows(h_def, WNDENUMPROC(fallback_cb), 0)
                if not top_candidate:
                    ctypes.windll.user32.EnumWindows(WNDENUMPROC(fallback_cb), 0)
            except Exception:
                pass
            if top_candidate:
                hwnd = top_candidate

        if not hwnd:
            return {
                "success": False,
                "error": "No foreground window found",
                "window": None,
            }

        title = _get_window_title(hwnd)
        class_name = _get_window_class(hwnd)
        pid = _get_window_pid(hwnd)
        bounds = _get_hwnd_rect(hwnd)
        is_minimized = _is_window_minimized(hwnd)
        is_visible = bool(ctypes.windll.user32.IsWindowVisible(hwnd))

        win = WindowInfo(
            hwnd=hwnd,
            process_id=pid,
            title=title,
            class_name=class_name,
            bounds=bounds,
            is_visible=is_visible,
            is_minimized=is_minimized,
        )
        return {"success": True, "window": win.to_dict(), "error": None}

    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": str(e), "window": None}


def find_window_by_title_substring(
    title_substring: str,
    bring_to_front: bool = True,
) -> tuple[int, str] | None:
    """
    Search all visible desktop windows across the interactive desktop for a window
    whose title contains `title_substring` (case-insensitive).

    If bring_to_front is True and a window is found, attempts to restore and foreground it.
    Returns (hwnd, title) or None.
    """
    if sys.platform != "win32" or not title_substring:
        return None
    try:
        ensure_interactive_desktop()
        user32 = ctypes.windll.user32
        target = title_substring.strip().lower()
        found: tuple[int, str] | None = None

        def search_cb(h, _):
            nonlocal found
            if is_real_visible_desktop_window(h):
                title = _get_window_title(h)
                if title and target in title.lower():
                    cls = _get_window_class(h)
                    if cls not in ("Progman", "Shell_TrayWnd", "Touch Tooltip Window"):
                        found = (int(h), title)
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        h_def = user32.OpenInputDesktop(0, False, 0x10000000) or user32.OpenDesktopW("Default", 0, False, 0x10000000)
        if h_def:
            user32.EnumDesktopWindows(h_def, WNDENUMPROC(search_cb), 0)
        if not found:
            user32.EnumWindows(WNDENUMPROC(search_cb), 0)

        if found and bring_to_front:
            hwnd, _ = found
            try:
                SW_RESTORE = 9
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        return found
    except Exception:
        return None


def get_element_tree(
    hwnd: int,
    depth: int = 3,
    max_elements: int = 200,
    timeout_sec: float = 5.0,
) -> dict[str, Any]:
    """
    Retrieve the UI element tree for a window using Windows UIA.

    Args:
        hwnd:          Window handle to inspect.
        depth:         Maximum traversal depth (default 3).
        max_elements:  Maximum number of elements to return (default 200).
        timeout_sec:   Traversal timeout in seconds (default 5).

    Returns:
        Dict with 'success', 'elements' (list of UIElement dicts), 'count', 'error'.
    """
    if not _is_window(hwnd):
        return {
            "success": False,
            "elements": [],
            "count": 0,
            "error": f"Invalid or closed window HWND: {hwnd}",
        }

    uia = _get_uia()
    if uia is None:
        return {
            "success": False,
            "elements": [],
            "count": 0,
            "error": _uia_error or "UIA not available",
        }

    try:
        import comtypes.gen.UIAutomationClient as UIA

        deadline = time.time() + timeout_sec
        elements: list[UIElement] = []
        seen_runtime_ids = set()
        window_title = _get_window_title(hwnd)
        pid = _get_window_pid(hwnd)
        counter = [0]  # mutable for nested function

        root_el = uia.ElementFromHandle(hwnd)
        if root_el is None:
            return {
                "success": False,
                "elements": [],
                "count": 0,
                "error": "UIA could not get element from HWND",
            }

        def _traverse(el, current_depth: int, parent_ct: str):
            if time.time() > deadline:
                return
            if counter[0] >= max_elements:
                return
            try:
                # Extract element properties safely
                ct_id = _safe_get(el, "CurrentControlType", 0)
                ct_name = UIA_CONTROL_TYPES.get(ct_id, f"Unknown({ct_id})")
                name = _safe_get(el, "CurrentName", "")
                auto_id = _safe_get(el, "CurrentAutomationId", "")
                enabled = _safe_get(el, "CurrentIsEnabled", True)
                offscreen = _safe_get(el, "CurrentIsOffscreen", False)
                focused = _safe_get(el, "CurrentHasKeyboardFocus", False)
                class_name = _safe_get(el, "CurrentClassName", "")

                # RuntimeId for cycle detection
                try:
                    runtime_id = str(list(el.GetRuntimeId()))
                except Exception:  # noqa: BLE001
                    runtime_id = f"{ct_id}:{name}:{auto_id}"

                if runtime_id in seen_runtime_ids:
                    return
                seen_runtime_ids.add(runtime_id)

                # Bounding rectangle
                try:
                    rect = el.CurrentBoundingRectangle
                    bounds = BoundingRect(
                        left=int(rect.left),
                        top=int(rect.top),
                        right=int(rect.right),
                        bottom=int(rect.bottom),
                    )
                except Exception:  # noqa: BLE001
                    bounds = BoundingRect()

                is_visible = not offscreen and bounds.is_valid

                # Try to read value text and discover available patterns
                text = ""
                available_patterns: list[str] = []
                toggle_state: str | None = None
                is_read_only: bool = False

                is_non_interactive = ct_name in NON_INTERACTIVE_CONTROL_TYPES
                is_unknown = ct_name.startswith("Unknown")

                if not is_non_interactive:
                    if is_unknown or ct_name in INVOKE_CAPABLE_TYPES:
                        try:
                            ip = el.GetCurrentPattern(UIA_INVOKE_PATTERN_ID)
                            if ip:
                                available_patterns.append("InvokePattern")
                        except Exception:  # noqa: BLE001, S110
                            pass

                    if is_unknown or ct_name in VALUE_TEXT_CAPABLE_TYPES:
                        try:
                            vp = el.GetCurrentPattern(UIA_VALUE_PATTERN_ID)
                            if vp:
                                available_patterns.append("ValuePattern")
                                vp_typed = vp.QueryInterface(
                                    UIA.IUIAutomationValuePattern
                                )
                                text = vp_typed.CurrentValue or ""
                                try:
                                    is_read_only = bool(vp_typed.CurrentIsReadOnly)
                                except Exception:  # noqa: BLE001
                                    is_read_only = False
                        except Exception:  # noqa: BLE001, S110
                            pass

                    if is_unknown or ct_name in TOGGLE_CAPABLE_TYPES:
                        try:
                            tp = el.GetCurrentPattern(UIA_TOGGLE_PATTERN_ID)
                            if tp:
                                available_patterns.append("TogglePattern")
                                tp_typed = tp.QueryInterface(
                                    UIA.IUIAutomationTogglePattern
                                )
                                ts_val = tp_typed.CurrentToggleState
                                toggle_state = {
                                    0: "OFF",
                                    1: "ON",
                                    2: "INDETERMINATE",
                                }.get(ts_val, str(ts_val))
                        except Exception:  # noqa: BLE001, S110
                            pass

                    if is_unknown or ct_name in SELECTION_EXPAND_CAPABLE_TYPES:
                        try:
                            if el.GetCurrentPattern(UIA_SELECTION_ITEM_PATTERN_ID):
                                available_patterns.append("SelectionItemPattern")
                        except Exception:  # noqa: BLE001, S110
                            pass

                        try:
                            if el.GetCurrentPattern(UIA_EXPAND_COLLAPSE_PATTERN_ID):
                                available_patterns.append("ExpandCollapsePattern")
                        except Exception:  # noqa: BLE001, S110
                            pass

                    if is_unknown or ct_name in SCROLL_CAPABLE_TYPES:
                        try:
                            if el.GetCurrentPattern(UIA_SCROLL_PATTERN_ID):
                                available_patterns.append("ScrollPattern")
                        except Exception:  # noqa: BLE001, S110
                            pass

                    if is_unknown or ct_name in VALUE_TEXT_CAPABLE_TYPES:
                        try:
                            if el.GetCurrentPattern(UIA_TEXT_PATTERN_ID):
                                available_patterns.append("TextPattern")
                        except Exception:  # noqa: BLE001, S110
                            pass

                element_id = f"e{counter[0]:04d}"
                uia_elem = UIElement(
                    element_id=element_id,
                    automation_id=auto_id,
                    runtime_id=runtime_id,
                    hwnd=hwnd,
                    process_id=pid,
                    window_title=window_title,
                    control_type=ct_name,
                    control_type_id=ct_id,
                    name=name,
                    text=text,
                    class_name=class_name,
                    is_enabled=bool(enabled),
                    is_visible=is_visible,
                    is_focused=bool(focused),
                    is_offscreen=bool(offscreen),
                    bounds=bounds,
                    parent_control_type=parent_ct,
                    depth=current_depth,
                    source="uia",
                    confidence=None,  # UIA is deterministic; no confidence score
                    available_patterns=available_patterns,
                    toggle_state=toggle_state,
                    is_read_only=is_read_only,
                )
                elements.append(uia_elem)
                counter[0] += 1

                # Recurse into children
                if current_depth < depth:
                    try:
                        children = uia.ControlViewWalker.GetFirstChildElement(el)
                        while children is not None:
                            if time.time() > deadline or counter[0] >= max_elements:
                                break
                            _traverse(children, current_depth + 1, ct_name)
                            try:
                                children = uia.ControlViewWalker.GetNextSiblingElement(
                                    children
                                )
                            except Exception:  # noqa: BLE001
                                break
                    except Exception:  # noqa: BLE001, S110
                        pass
            except Exception:  # noqa: BLE001, S110
                pass  # Skip malformed elements silently

        _traverse(root_el, 0, "")

        return {
            "success": True,
            "elements": [e.to_dict() for e in elements],
            "count": len(elements),
            "error": None,
            "hwnd": hwnd,
            "window_title": window_title,
        }

    except Exception as e:  # noqa: BLE001
        return {"success": False, "elements": [], "count": 0, "error": str(e)}


def _safe_get(el, attr: str, default):
    """Safely get a UIA element attribute without raising."""
    try:
        return getattr(el, attr)
    except Exception:  # noqa: BLE001
        return default


def find_element_by_name(hwnd: int, name: str, exact: bool = False) -> dict[str, Any]:
    """
    Find first element in the window whose name matches (case-insensitive substring by default).

    Args:
        hwnd:  Window handle.
        name:  Name to search.
        exact: If True, require exact case-insensitive match.

    Returns:
        Dict with 'found' bool, 'element' dict or None, 'error'.
    """
    result = get_element_tree(hwnd, depth=4, max_elements=300)
    if not result["success"]:
        return {"found": False, "element": None, "error": result.get("error")}

    name_lower = name.lower()
    for el_dict in result["elements"]:
        el_name = el_dict.get("name", "").lower()
        if exact:
            if el_name == name_lower:
                return {"found": True, "element": el_dict, "error": None}
        else:
            if name_lower in el_name:
                return {"found": True, "element": el_dict, "error": None}

    return {
        "found": False,
        "element": None,
        "error": f"No element with name '{name}' found in window {hwnd}",
    }


def find_element_by_type(hwnd: int, control_type: str) -> dict[str, Any]:
    """
    Find all elements in the window matching a control type (case-insensitive).

    Returns:
        Dict with 'elements' list, 'count', 'error'.
    """
    result = get_element_tree(hwnd, depth=4, max_elements=300)
    if not result["success"]:
        return {"elements": [], "count": 0, "error": result.get("error")}

    ct_lower = control_type.lower()
    matched = [
        e for e in result["elements"] if e.get("control_type", "").lower() == ct_lower
    ]
    return {"elements": matched, "count": len(matched), "error": None}


def revalidate_element(ref_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Attempt to revalidate an ElementReference by re-querying UIA.
    Used by the action dispatcher before executing any action.

    Returns:
        Dict with 'valid' bool, 'element' dict or None, 'reason' string.
    """
    hwnd = ref_dict.get("hwnd", 0)
    if not hwnd or not _is_window(hwnd):
        return {
            "valid": False,
            "element": None,
            "reason": f"HWND {hwnd} is no longer valid",
        }

    runtime_id = ref_dict.get("runtime_id", "")
    auto_id = ref_dict.get("automation_id", "")
    name = ref_dict.get("name", "")
    control_type = ref_dict.get("control_type", "")

    result = get_element_tree(hwnd, depth=5, max_elements=400)
    if not result["success"]:
        return {
            "valid": False,
            "element": None,
            "reason": f"UIA traversal failed: {result.get('error')}",
        }

    for el in result["elements"]:
        # Match by runtime_id first (most reliable within session)
        if runtime_id and el.get("runtime_id") == runtime_id:
            if el.get("is_enabled") and el.get("is_visible"):
                return {"valid": True, "element": el, "reason": "Matched by runtime_id"}
            else:
                return {
                    "valid": False,
                    "element": el,
                    "reason": "Element found but is disabled or invisible",
                }

    # Fallback: match by automation_id + control_type + name
    for el in result["elements"]:
        match = (
            (not auto_id or el.get("automation_id") == auto_id)
            and (
                not control_type
                or el.get("control_type", "").lower() == control_type.lower()
            )
            and (not name or el.get("name", "").lower() == name.lower())
        )
        if match:
            if el.get("is_enabled") and el.get("is_visible"):
                return {
                    "valid": True,
                    "element": el,
                    "reason": "Matched by automation_id/type/name fallback",
                }
            else:
                return {
                    "valid": False,
                    "element": el,
                    "reason": "Fallback match found but element is disabled or invisible",
                }

    return {
        "valid": False,
        "element": None,
        "reason": "Element not found in current window state",
    }
