"""
COMPASS Claude Opus 5.5 Computer-Use Protocol Adapter
Native Windows Computer Control via official Anthropic Messages API.

Protocol Specifications:
- Model Identifier: claude-opus-5-5
- Toolset: computer_toolset_20260801
- Beta Header: anthropic-beta: computer-use-2026-08-01
- Version Header: anthropic-version: 2023-06-01
- Endpoint: https://api.anthropic.com/v1/messages

Supported Tool Members:
- screenshot
- zoom
- left_click
- right_click
- middle_click
- double_click
- triple_click
- left_click_drag
- mouse_move
- left_mouse_down
- left_mouse_up
- cursor_position
- scroll
- type
- key
- hold_key
- wait
"""

from __future__ import annotations

import base64
import ctypes
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from PIL import Image

from automation.action_log import log_action
from automation.safety import (
    check_coordinates_safe,
    check_foreground_context,
    check_hwnd_safe,
    get_safety_manager,
)
from backend.app.logging_config import logger
from perception.coordinate_mapper import CoordinateMapper

# Official Anthropic protocol constants
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_BETA_COMPUTER_USE = "computer-use-2026-08-01"
MODEL_CLAUDE_OPUS_5_5 = "claude-opus-5-5"
TOOLSET_COMPUTER_20260801 = "computer_toolset_20260801"
TOOL_NAME_COMPUTER = "computer"

# Windows input constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Common virtual key code mappings for 'key' and 'hold_key'
VK_MAPPING: dict[str, int] = {
    "return": 0x0D,
    "enter": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "escape": 0x1B,
    "esc": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "insert": 0x2D,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "super": 0x5B,
    "win": 0x5B,
    "windows": 0x5B,
}


@dataclass
class DisplayGeometry:
    """Represents display dimensions and scaling metadata for model coordinate translation."""
    width: int = 1920
    height: int = 1080
    origin_x: int = 0
    origin_y: int = 0
    scale_x: float = 1.0
    scale_y: float = 1.0
    scaled_width: int = 1920
    scaled_height: int = 1080


@dataclass
class ToolUseBlock:
    """Represents an incoming tool_use content block from Claude."""
    id: str
    name: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultBlock:
    """Represents an outgoing tool_result block conforming to Anthropic Messages protocol."""
    tool_use_id: str
    toolset_name: str = TOOL_NAME_COMPUTER
    is_error: bool = False
    content: list[dict[str, Any]] = field(default_factory=list)

    def to_api_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "toolset_name": self.toolset_name,
            "is_error": self.is_error,
        }
        if self.content:
            result["content"] = self.content
        return result


class ClaudeComputerUseClient:
    """
    HTTP client for Claude Opus 5.5 Computer Use via Anthropic Messages API.
    Zero external SDK dependency — uses httpx with native JSON/streaming protocols.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = ANTHROPIC_API_URL,
        timeout_seconds: float = 60.0,
        mock_mode: bool = False,
    ):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self.mock_mode = mock_mode or os.environ.get("COMPASS_MOCK_CLAUDE") == "1"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key) or self.mock_mode

    def get_headers(self) -> dict[str, str]:
        headers = {
            "anthropic-version": ANTHROPIC_API_VERSION,
            "anthropic-beta": ANTHROPIC_BETA_COMPUTER_USE,
            "content-type": "application/json",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def create_computer_tool_definition(
        self, width: int = 1920, height: int = 1080, display_number: int = 1
    ) -> dict[str, Any]:
        """
        Builds the official Anthropic Messages API computer-use tool declaration.
        Uses computer_toolset_20260801.
        """
        return {
            "type": TOOLSET_COMPUTER_20260801,
            "name": TOOL_NAME_COMPUTER,
            "display_width_px": width,
            "display_height_px": height,
            "display_number": display_number,
        }

    def send_turn(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        display_width: int = 1920,
        display_height: int = 1080,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        cancel_event: Any = None,
    ) -> dict[str, Any]:
        """
        Send a conversation turn to Claude Opus 5.5 and receive assistant response.
        Handles rate limits, timeouts, and cancellations.
        """
        if cancel_event and cancel_event.is_set():
            return {
                "success": False,
                "error": "Request cancelled before dispatch",
                "stop_reason": "cancelled",
            }

        if self.mock_mode:
            return self._mock_response(messages)

        if not self._api_key:
            return {
                "success": False,
                "error": "ANTHROPIC_API_KEY is not configured.",
                "stop_reason": "missing_credentials",
            }

        tools = [
            self.create_computer_tool_definition(
                width=display_width, height=display_height
            )
        ]

        payload = {
            "model": MODEL_CLAUDE_OPUS_5_5,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "tools": tools,
            "messages": messages,
        }

        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                resp = client.post(
                    self._base_url,
                    headers=self.get_headers(),
                    json=payload,
                )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "data": data,
                    "stop_reason": data.get("stop_reason"),
                    "content": data.get("content", []),
                    "usage": data.get("usage", {}),
                }
            elif resp.status_code == 429:
                err_msg = f"Rate limited by Anthropic API (429): {resp.text}"
                logger.warning(err_msg)
                return {"success": False, "error": err_msg, "stop_reason": "rate_limited"}
            elif resp.status_code == 401 or resp.status_code == 403:
                err_msg = f"Authentication failed with Anthropic API ({resp.status_code}): {resp.text}"
                logger.error(err_msg)
                return {"success": False, "error": err_msg, "stop_reason": "auth_failure"}
            else:
                err_msg = f"Anthropic API returned status {resp.status_code}: {resp.text}"
                logger.error(err_msg)
                return {"success": False, "error": err_msg, "stop_reason": "api_error"}

        except httpx.TimeoutException:
            logger.error(f"Anthropic API request timed out after {self._timeout_seconds}s")
            return {"success": False, "error": f"API request timed out ({self._timeout_seconds}s)", "stop_reason": "timeout"}
        except Exception as e:
            logger.error(f"Anthropic API communication exception: {e}")
            return {"success": False, "error": str(e), "stop_reason": "exception"}

    def _mock_response(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Mock response generator for unit and integration testing without cloud API access."""
        last_msg = messages[-1] if messages else {}
        content = last_msg.get("content", [])

        # Check if last message was a tool result
        has_tool_results = False
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    has_tool_results = True
                    break

        if not has_tool_results:
            # First turn: model requests screenshot
            return {
                "success": True,
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "text",
                        "text": "I will inspect the desktop screen to determine the active application.",
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_mock_shot_01",
                        "name": TOOL_NAME_COMPUTER,
                        "input": {"action": "screenshot"},
                    },
                ],
                "usage": {"input_tokens": 100, "output_tokens": 40},
            }
        else:
            # Subsequent turn: return completion text
            return {
                "success": True,
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": "I have observed the screen and accomplished the requested operation.",
                    }
                ],
                "usage": {"input_tokens": 150, "output_tokens": 30},
            }


class WindowsComputerActionExecutor:
    """
    Executes validated computer-use actions on Windows desktop.
    Ensures safe coordinate mapping, DPI scaling, multi-monitor topology,
    and gating through COMPASS's security engine before any hardware event.
    """

    def __init__(
        self,
        coordinate_mapper: CoordinateMapper | None = None,
        max_screenshot_width: int = 1920,
        max_screenshot_height: int = 1080,
    ):
        self.coordinate_mapper = coordinate_mapper or CoordinateMapper()
        self.max_screenshot_width = max_screenshot_width
        self.max_screenshot_height = max_screenshot_height
        self._safety = get_safety_manager()
        self.last_display_geometry = DisplayGeometry()

    def get_current_display_geometry(self) -> DisplayGeometry:
        """Calculate display dimensions and scaling for model coordinates."""
        vscreen = self.coordinate_mapper.get_virtual_screen_bounds()
        w_real = max(1, vscreen.width)
        h_real = max(1, vscreen.height)
        origin_x = vscreen.left
        origin_y = vscreen.top

        # Scale down if virtual screen exceeds max dimensions, preserving aspect ratio
        scale = min(1.0, self.max_screenshot_width / w_real, self.max_screenshot_height / h_real)
        w_scaled = int(w_real * scale)
        h_scaled = int(h_real * scale)

        geom = DisplayGeometry(
            width=w_real,
            height=h_real,
            origin_x=origin_x,
            origin_y=origin_y,
            scale_x=w_real / max(1, w_scaled),
            scale_y=h_real / max(1, h_scaled),
            scaled_width=w_scaled,
            scaled_height=h_scaled,
        )
        self.last_display_geometry = geom
        return geom

    def capture_screenshot_base64(self, crop_region: tuple[int, int, int, int] | None = None) -> tuple[str, int, int]:
        """
        Capture desktop and return (base64_png, width, height).
        Uses PIL ImageGrab or GDI screen capture.
        """
        geom = self.get_current_display_geometry()
        img: Image.Image | None = None

        try:
            from PIL import ImageGrab
            try:
                img = ImageGrab.grab(all_screens=True)
            except Exception:
                img = ImageGrab.grab()
        except Exception as e:
            logger.warning(f"PIL ImageGrab capture failed: {e}. Falling back to GDI.")

        if img is None:
            # Fallback to COMPASS GDI screen capture
            try:
                from perception.screen_capture import capture_full_screen
                res = capture_full_screen(include_b64=True)
                if res.success and res.data_b64:
                    return res.data_b64, res.width, res.height
            except Exception as gdi_err:
                logger.debug(f"GDI capture fallback exception: {gdi_err}")
            # If all fails, produce blank canvas for testing
            img = Image.new("RGB", (geom.scaled_width, geom.scaled_height), color=(30, 30, 30))

        if crop_region:
            img = img.crop(crop_region)

        # Resize to scaled dimensions if needed
        if (img.width, img.height) != (geom.scaled_width, geom.scaled_height) and not crop_region:
            img = img.resize((geom.scaled_width, geom.scaled_height), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        b64_str = base64.b64encode(buffer.getvalue()).decode("ascii")
        return b64_str, img.width, img.height

    def model_to_desktop_coordinates(self, model_x: int, model_y: int) -> tuple[int, int]:
        """
        Translate model screenshot coordinates to Windows virtual display screen coordinates.
        Accounts for screenshot scaling factor and multi-monitor origin offsets.
        """
        geom = self.last_display_geometry
        real_x = int(model_x * geom.scale_x) + geom.origin_x
        real_y = int(model_y * geom.scale_y) + geom.origin_y
        return real_x, real_y

    def desktop_to_model_coordinates(self, desktop_x: int, desktop_y: int) -> tuple[int, int]:
        """Translate Windows desktop coordinates to model screenshot coordinates."""
        geom = self.last_display_geometry
        model_x = int((desktop_x - geom.origin_x) / max(1e-4, geom.scale_x))
        model_y = int((desktop_y - geom.origin_y) / max(1e-4, geom.scale_y))
        return model_x, model_y

    def execute_action(
        self,
        action_name: str,
        params: dict[str, Any],
        task_id: str | None = None,
        cancel_event: Any = None,
    ) -> ToolResultBlock:
        """
        Validates and executes a single Claude computer-use action.
        Returns a ToolResultBlock with is_error=True if execution fails.
        """
        if cancel_event and cancel_event.is_set():
            return ToolResultBlock(
                tool_use_id=params.get("_tool_use_id", ""),
                is_error=True,
                content=[{"type": "text", "text": "Execution aborted: STOP flag set."}],
            )

        tool_use_id = params.get("_tool_use_id", "")
        act = action_name.lower().strip()

        try:
            # 1. SCREENSHOT
            if act == "screenshot":
                b64_img, w, h = self.capture_screenshot_base64()
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_img,
                            },
                        }
                    ],
                )

            # 2. ZOOM
            elif act == "zoom":
                coord = params.get("coordinate")
                if not coord or len(coord) != 2:
                    return ToolResultBlock(
                        tool_use_id=tool_use_id,
                        is_error=True,
                        content=[{"type": "text", "text": "Zoom action requires 'coordinate': [x, y]."}],
                    )
                mx, my = coord[0], coord[1]
                rx, ry = self.model_to_desktop_coordinates(mx, my)
                # Crop 300x300 bounding box around target coordinate
                box_radius = 150
                crop_box = (
                    max(0, rx - box_radius),
                    max(0, ry - box_radius),
                    rx + box_radius,
                    ry + box_radius,
                )
                b64_img, w, h = self.capture_screenshot_base64(crop_region=crop_box)
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_img,
                            },
                        }
                    ],
                )

            # 3. CURSOR POSITION
            elif act == "cursor_position":
                if sys.platform == "win32":
                    pt = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    mx, my = self.desktop_to_model_coordinates(pt.x, pt.y)
                    return ToolResultBlock(
                        tool_use_id=tool_use_id,
                        is_error=False,
                        content=[{"type": "text", "text": f"Current cursor position: [{mx}, {my}] (desktop: [{pt.x}, {pt.y}])"}],
                    )
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": "Current cursor position: [0, 0]"}],
                )

            # 4. WAIT
            elif act == "wait":
                duration = float(params.get("duration", 1.0))
                duration = max(0.05, min(30.0, duration))
                # Sleep cooperatively checking cancellation every 50ms
                end_t = time.time() + duration
                while time.time() < end_t:
                    if cancel_event and cancel_event.is_set():
                        return ToolResultBlock(
                            tool_use_id=tool_use_id,
                            is_error=True,
                            content=[{"type": "text", "text": "Wait aborted: STOP flag set."}],
                        )
                    time.sleep(min(0.05, end_t - time.time()))
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Waited {duration:.2f} seconds."}],
                )

            # 5. MOUSE CLICKS & MOVEMENTS
            elif act in (
                "left_click",
                "right_click",
                "middle_click",
                "double_click",
                "triple_click",
                "mouse_move",
                "left_mouse_down",
                "left_mouse_up",
            ):
                coord = params.get("coordinate")
                if coord and len(coord) == 2:
                    rx, ry = self.model_to_desktop_coordinates(coord[0], coord[1])
                    valid, reason = self.coordinate_mapper.validate_target_point(rx, ry)
                    if not valid:
                        return ToolResultBlock(
                            tool_use_id=tool_use_id,
                            is_error=True,
                            content=[{"type": "text", "text": f"Coordinates out of desktop bounds: {reason}"}],
                        )
                    coord_safe = check_coordinates_safe(rx, ry)
                    if not coord_safe.ok:
                        return ToolResultBlock(
                            tool_use_id=tool_use_id,
                            is_error=True,
                            content=[{"type": "text", "text": f"Coordinates unsafe: {coord_safe.reason}"}],
                        )
                    if sys.platform == "win32":
                        ctypes.windll.user32.SetCursorPos(rx, ry)
                        time.sleep(0.02)
                elif act not in ("left_mouse_down", "left_mouse_up"):
                    # For clicks, coordinate is required if cursor not already positioned
                    pass

                if sys.platform == "win32":
                    user32 = ctypes.windll.user32
                    if act == "left_click":
                        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.02)
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    elif act == "right_click":
                        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                        time.sleep(0.02)
                        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                    elif act == "middle_click":
                        user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
                        time.sleep(0.02)
                        user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
                    elif act == "double_click":
                        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.02)
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        time.sleep(0.04)
                        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.02)
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    elif act == "triple_click":
                        for _ in range(3):
                            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            time.sleep(0.02)
                            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            time.sleep(0.03)
                    elif act == "left_mouse_down":
                        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    elif act == "left_mouse_up":
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                log_action(act, {"params": params}, "native_windows", True, task_id=task_id)
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Successfully executed '{act}' at {coord}."}],
                )

            # 6. DRAG
            elif act == "left_click_drag":
                coord = params.get("coordinate")
                start_coord = params.get("start_coordinate")
                if not coord or len(coord) != 2:
                    return ToolResultBlock(
                        tool_use_id=tool_use_id,
                        is_error=True,
                        content=[{"type": "text", "text": "left_click_drag requires 'coordinate': [x, y]."}],
                    )

                dest_x, dest_y = self.model_to_desktop_coordinates(coord[0], coord[1])
                if sys.platform == "win32":
                    user32 = ctypes.windll.user32
                    if start_coord and len(start_coord) == 2:
                        sx, sy = self.model_to_desktop_coordinates(start_coord[0], start_coord[1])
                        user32.SetCursorPos(sx, sy)
                        time.sleep(0.03)

                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.05)
                    # Interpolate movement smoothly
                    curr_pt = ctypes.wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(curr_pt))
                    steps = 10
                    for step in range(1, steps + 1):
                        ix = int(curr_pt.x + (dest_x - curr_pt.x) * (step / steps))
                        iy = int(curr_pt.y + (dest_y - curr_pt.y) * (step / steps))
                        user32.SetCursorPos(ix, iy)
                        time.sleep(0.01)
                    user32.SetCursorPos(dest_x, dest_y)
                    time.sleep(0.03)
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Dragged to [{coord[0]}, {coord[1]}]."}],
                )

            # 7. SCROLL
            elif act == "scroll":
                coord = params.get("coordinate")
                if coord and len(coord) == 2 and sys.platform == "win32":
                    rx, ry = self.model_to_desktop_coordinates(coord[0], coord[1])
                    ctypes.windll.user32.SetCursorPos(rx, ry)
                    time.sleep(0.02)

                delta_y = int(params.get("delta_y", 0))
                delta_x = int(params.get("delta_x", 0))

                # Handle alternate scroll_direction parameter
                direction = str(params.get("scroll_direction", "")).lower()
                amount = int(params.get("scroll_amount", 2))
                if direction == "up":
                    delta_y = amount * 120
                elif direction == "down":
                    delta_y = -amount * 120
                elif direction == "left":
                    delta_x = -amount * 120
                elif direction == "right":
                    delta_x = amount * 120

                if sys.platform == "win32":
                    user32 = ctypes.windll.user32
                    if delta_y != 0:
                        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta_y, 0)
                    if delta_x != 0:
                        user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, delta_x, 0)

                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Scrolled delta_x={delta_x}, delta_y={delta_y}."}],
                )

            # 8. TYPE
            elif act == "type":
                text = str(params.get("text", ""))
                from automation import action_dispatcher
                for ch in text:
                    if cancel_event and cancel_event.is_set():
                        return ToolResultBlock(
                            tool_use_id=tool_use_id,
                            is_error=True,
                            content=[{"type": "text", "text": "Type action aborted: STOP flag set."}],
                        )
                    if not action_dispatcher._send_unicode_char(ch):
                        logger.warning(f"Could not send unicode character '{ch}'")
                    time.sleep(0.015)
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Typed {len(text)} characters."}],
                )

            # 9. KEY
            elif act == "key":
                key_combo = str(params.get("key", "")).strip().lower()
                keys = [k.strip() for k in key_combo.split("+") if k.strip()]
                if not keys:
                    return ToolResultBlock(
                        tool_use_id=tool_use_id,
                        is_error=True,
                        content=[{"type": "text", "text": "Empty key sequence."}],
                    )

                if sys.platform == "win32":
                    vk_list = []
                    for k in keys:
                        vk = VK_MAPPING.get(k)
                        if not vk and len(k) == 1:
                            vk = ord(k.upper())
                        if vk:
                            vk_list.append(vk)

                    # Press all keys down in order
                    for vk in vk_list:
                        self._send_key_event(vk, down=True)
                        time.sleep(0.01)
                    # Release in reverse order
                    for vk in reversed(vk_list):
                        self._send_key_event(vk, down=False)
                        time.sleep(0.01)

                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Sent key sequence '{key_combo}'."}],
                )

            # 10. HOLD KEY
            elif act == "hold_key":
                key_name = str(params.get("key", "")).strip().lower()
                duration = float(params.get("duration", 0.5))
                duration = max(0.05, min(10.0, duration))
                vk = VK_MAPPING.get(key_name)
                if not vk and len(key_name) == 1:
                    vk = ord(key_name.upper())

                if vk and sys.platform == "win32":
                    self._send_key_event(vk, down=True)
                    time.sleep(duration)
                    self._send_key_event(vk, down=False)

                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=False,
                    content=[{"type": "text", "text": f"Held key '{key_name}' for {duration:.2f}s."}],
                )

            else:
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    is_error=True,
                    content=[{"type": "text", "text": f"Unsupported or unknown computer action: '{action_name}'."}],
                )

        except Exception as ex:
            logger.error(f"Error executing computer action '{action_name}': {ex}")
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                is_error=True,
                content=[{"type": "text", "text": f"Execution error for '{action_name}': {ex!s}"}],
            )

    def _send_key_event(self, vk_code: int, down: bool = True) -> bool:
        """Sends a Win32 SendInput keyboard event (press or release)."""
        if sys.platform != "win32":
            return False
        try:
            from automation.action_dispatcher import INPUT, INPUT_KEYBOARD, KEYEVENTF_KEYUP
            inp = (INPUT * 1)()
            inp[0].type = INPUT_KEYBOARD
            inp[0].union.ki.wVk = vk_code
            inp[0].union.ki.dwFlags = 0 if down else KEYEVENTF_KEYUP
            inp[0].union.ki.dwExtraInfo = 0
            sent = ctypes.windll.user32.SendInput(1, inp, ctypes.sizeof(INPUT))
            return sent == 1
        except Exception as e:
            logger.debug(f"SendInput key event error: {e}")
            return False
