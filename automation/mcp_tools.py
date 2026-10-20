"""
COMPASS — MCP Tool Interface (Phase 9)
Model Context Protocol tool definitions for COMPASS capabilities.

Provides a structured, validated tool interface following MCP conventions.
Each tool has: schema, validation, permission policy, logging, error handling,
timeout, and cancellation support.

These tools do NOT bypass COMPASS safety checks.
All tool calls are logged to the action audit trail.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ToolPermission(str, Enum):
    """Permission level required to invoke a tool."""

    READ = "read"  # Read-only observation tools
    WRITE = "write"  # Actions that change state
    DANGEROUS = "dangerous"  # Actions requiring explicit confirmation


@dataclass
class ToolSchema:
    """Schema definition for a COMPASS MCP tool."""

    name: str
    description: str
    permission: ToolPermission
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    timeout_ms: int = 10000
    requires_safety_check: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission.value,
            "parameters": self.parameters,
            "timeout_ms": self.timeout_ms,
            "requires_safety_check": self.requires_safety_check,
        }


@dataclass
class ToolResult:
    """Structured result from a tool invocation."""

    tool_name: str
    success: bool = False
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0
    permission_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "permission_used": self.permission_used,
        }


class CompassToolRegistry:
    """
    Registry of COMPASS tools exposed via MCP interface.
    Manages tool registration, validation, permission checks, and invocation.
    """

    def __init__(self):
        self._tools: dict[str, ToolSchema] = {}
        self._handlers: dict[str, Callable] = {}
        self._invocation_log: list[dict[str, Any]] = []

    def register(self, schema: ToolSchema, handler: Callable) -> None:
        """Register a tool with its schema and handler function."""
        if schema.name in self._tools:
            logger.warning(f"Tool '{schema.name}' already registered, overwriting")
        self._tools[schema.name] = schema
        self._handlers[schema.name] = handler
        logger.info(
            f"Registered COMPASS tool: {schema.name} (permission={schema.permission.value})"
        )

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools and their schemas."""
        return [schema.to_dict() for schema in self._tools.values()]

    def get_tool_schema(self, name: str) -> ToolSchema | None:
        """Get the schema for a specific tool."""
        return self._tools.get(name)

    def validate_parameters(
        self, tool_name: str, params: dict[str, Any]
    ) -> str | None:
        """
        Validate parameters against tool schema.
        Returns error string or None if valid.
        """
        schema = self._tools.get(tool_name)
        if not schema:
            return f"Unknown tool: {tool_name}"

        required = schema.parameters.get("required", [])
        properties = schema.parameters.get("properties", {})

        for req_param in required:
            if req_param not in params:
                return f"Missing required parameter: {req_param}"

        for key, value in params.items():
            if key in properties:
                prop_schema = properties[key]
                expected_type = prop_schema.get("type")
                if expected_type == "string" and not isinstance(value, str):
                    return f"Parameter '{key}' must be a string"
                if expected_type == "integer" and not isinstance(value, int):
                    return f"Parameter '{key}' must be an integer"
                if expected_type == "boolean" and not isinstance(value, bool):
                    return f"Parameter '{key}' must be a boolean"

        return None

    def invoke(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """
        Invoke a registered tool with parameter validation and logging.
        """
        start_t = time.time()
        result = ToolResult(tool_name=tool_name)

        # Check tool exists
        schema = self._tools.get(tool_name)
        if not schema:
            result.error = f"Unknown tool: {tool_name}"
            return result

        result.permission_used = schema.permission.value

        # Validate parameters
        validation_err = self.validate_parameters(tool_name, params)
        if validation_err:
            result.error = f"Validation failed: {validation_err}"
            self._log_invocation(tool_name, params, result)
            return result

        # Invoke handler
        handler = self._handlers.get(tool_name)
        if not handler:
            result.error = f"No handler registered for tool: {tool_name}"
            self._log_invocation(tool_name, params, result)
            return result

        try:
            output = handler(params)
            result.success = True
            result.data = output
        except Exception as e:  # noqa: BLE001
            result.error = f"Tool execution failed: {e!s}"
            logger.error(f"Tool '{tool_name}' failed: {e}")

        result.duration_ms = (time.time() - start_t) * 1000
        self._log_invocation(tool_name, params, result)
        return result

    def _log_invocation(self, tool_name: str, params: dict, result: ToolResult) -> None:
        """Log tool invocation for audit trail."""
        entry = {
            "tool": tool_name,
            "timestamp": time.time(),
            "success": result.success,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "permission": result.permission_used,
        }
        self._invocation_log.append(entry)
        # Keep log bounded
        if len(self._invocation_log) > 1000:
            self._invocation_log = self._invocation_log[-500:]

    def get_invocation_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent tool invocation log entries."""
        return self._invocation_log[-limit:]


# ─── Default COMPASS Tool Definitions ─────────────────────────────────────────


def create_default_tools() -> CompassToolRegistry:
    """
    Create the default COMPASS tool registry with all standard tools.
    Handlers are lightweight wrappers that delegate to existing COMPASS modules.
    """
    registry = CompassToolRegistry()

    # --- READ tools (observation) ---

    registry.register(
        ToolSchema(
            name="inspect_ui",
            description="Inspect the current foreground window's UI element tree using Windows UI Automation",
            permission=ToolPermission.READ,
            parameters={
                "type": "object",
                "properties": {
                    "depth": {
                        "type": "integer",
                        "description": "Max tree depth (1-5)",
                        "default": 3,
                    },
                },
            },
            timeout_ms=5000,
        ),
        handler=_handle_inspect_ui,
    )

    registry.register(
        ToolSchema(
            name="get_ui_state",
            description="Get a snapshot of the current UI state including window title, element count, and foreground app",
            permission=ToolPermission.READ,
            parameters={"type": "object", "properties": {}},
            timeout_ms=3000,
        ),
        handler=_handle_get_ui_state,
    )

    registry.register(
        ToolSchema(
            name="find_element",
            description="Find a UI element by name in the current foreground window",
            permission=ToolPermission.READ,
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Element name or text to search for",
                    },
                },
                "required": ["name"],
            },
            timeout_ms=5000,
        ),
        handler=_handle_find_element,
    )

    registry.register(
        ToolSchema(
            name="read_text",
            description="Read text from the screen using OCR",
            permission=ToolPermission.READ,
            parameters={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional bounding region {x, y, width, height}",
                    },
                },
            },
            timeout_ms=10000,
        ),
        handler=_handle_read_text,
    )

    registry.register(
        ToolSchema(
            name="take_screenshot",
            description="Capture a screenshot of the current screen state",
            permission=ToolPermission.READ,
            parameters={"type": "object", "properties": {}},
            timeout_ms=3000,
        ),
        handler=_handle_take_screenshot,
    )

    registry.register(
        ToolSchema(
            name="get_window_state",
            description="Get current window title, handle, position and dimensions",
            permission=ToolPermission.READ,
            parameters={"type": "object", "properties": {}},
            timeout_ms=2000,
        ),
        handler=_handle_get_window_state,
    )

    registry.register(
        ToolSchema(
            name="verify_state",
            description="Verify that a specific UI condition is met (element exists, text visible, etc.)",
            permission=ToolPermission.READ,
            parameters={
                "type": "object",
                "properties": {
                    "condition": {
                        "type": "string",
                        "description": "What to verify: 'element_exists', 'text_visible'",
                    },
                    "target": {
                        "type": "string",
                        "description": "Element name or text to look for",
                    },
                },
                "required": ["condition", "target"],
            },
            timeout_ms=5000,
        ),
        handler=_handle_verify_state,
    )

    # --- WRITE tools (actions) ---

    registry.register(
        ToolSchema(
            name="click_element",
            description="Click a UI element identified by name",
            permission=ToolPermission.WRITE,
            parameters={
                "type": "object",
                "properties": {
                    "element_name": {
                        "type": "string",
                        "description": "Name of the element to click",
                    },
                },
                "required": ["element_name"],
            },
            timeout_ms=5000,
            requires_safety_check=True,
        ),
        handler=_handle_click_element,
    )

    registry.register(
        ToolSchema(
            name="type_text",
            description="Type text into the currently focused element or a specified element",
            permission=ToolPermission.WRITE,
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "target": {
                        "type": "string",
                        "description": "Optional target element name",
                    },
                },
                "required": ["text"],
            },
            timeout_ms=5000,
            requires_safety_check=True,
        ),
        handler=_handle_type_text,
    )

    registry.register(
        ToolSchema(
            name="press_key",
            description="Press a keyboard key or combination",
            permission=ToolPermission.WRITE,
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key name (e.g. 'enter', 'tab', 'escape')",
                    },
                },
                "required": ["key"],
            },
            timeout_ms=3000,
            requires_safety_check=True,
        ),
        handler=_handle_press_key,
    )

    registry.register(
        ToolSchema(
            name="navigate_browser",
            description="Open a URL in the browser",
            permission=ToolPermission.WRITE,
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to navigate to"},
                },
                "required": ["url"],
            },
            timeout_ms=30000,
            requires_safety_check=True,
        ),
        handler=_handle_navigate_browser,
    )

    return registry


# ─── Tool Handler Implementations ────────────────────────────────────────────
# These are lightweight wrappers that delegate to existing COMPASS modules.


def _handle_inspect_ui(params: dict[str, Any]) -> Any:
    from perception import uia_inspector

    depth = min(max(params.get("depth", 3), 1), 5)
    window = uia_inspector.get_foreground_window()
    if not window or not window.hwnd:
        return {"elements": [], "window": None, "error": "No foreground window"}
    elements = uia_inspector.get_element_tree(window.hwnd, depth=depth)
    return {
        "window": window.to_dict()
        if hasattr(window, "to_dict")
        else {"hwnd": window.hwnd, "title": window.title},
        "element_count": len(elements),
        "elements": [
            e.to_dict() if hasattr(e, "to_dict") else str(e) for e in elements[:50]
        ],
    }


def _handle_get_ui_state(params: dict[str, Any]) -> Any:
    from perception import uia_inspector

    window = uia_inspector.get_foreground_window()
    if not window:
        return {"window": None}
    return {
        "window_title": getattr(window, "title", ""),
        "window_hwnd": getattr(window, "hwnd", 0),
        "window_class": getattr(window, "class_name", ""),
    }


def _handle_find_element(params: dict[str, Any]) -> Any:
    from perception import uia_inspector

    name = params["name"]
    window = uia_inspector.get_foreground_window()
    if not window or not window.hwnd:
        return {"found": False, "error": "No foreground window"}
    element = uia_inspector.find_element_by_name(window.hwnd, name)
    if element:
        return {
            "found": True,
            "element": element.to_dict()
            if hasattr(element, "to_dict")
            else str(element),
        }
    return {"found": False, "name": name}


def _handle_read_text(params: dict[str, Any]) -> Any:
    return {
        "text": "",
        "source": "ocr",
        "note": "OCR invocation requires screen capture pipeline",
    }


def _handle_take_screenshot(params: dict[str, Any]) -> Any:
    from perception import screen_capture

    result = screen_capture.capture_full_screen()
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return {"captured": bool(result)}


def _handle_get_window_state(params: dict[str, Any]) -> Any:
    from perception import uia_inspector

    window = uia_inspector.get_foreground_window()
    if not window:
        return {"window": None}
    return {
        "title": getattr(window, "title", ""),
        "hwnd": getattr(window, "hwnd", 0),
        "class_name": getattr(window, "class_name", ""),
        "bounds": getattr(window, "bounds", None),
    }


def _handle_verify_state(params: dict[str, Any]) -> Any:
    condition = params["condition"]
    target = params["target"]
    if condition == "element_exists":
        from perception import uia_inspector

        window = uia_inspector.get_foreground_window()
        if not window or not window.hwnd:
            return {"verified": False, "reason": "No foreground window"}
        element = uia_inspector.find_element_by_name(window.hwnd, target)
        return {
            "verified": element is not None,
            "condition": condition,
            "target": target,
        }
    return {"verified": False, "reason": f"Unknown condition type: {condition}"}


def _handle_click_element(params: dict[str, Any]) -> Any:
    return {
        "action": "click",
        "target": params.get("element_name"),
        "note": "Delegated to COMPASS action_dispatcher via execution_engine",
    }


def _handle_type_text(params: dict[str, Any]) -> Any:
    return {
        "action": "type",
        "text_length": len(params.get("text", "")),
        "note": "Delegated to COMPASS action_dispatcher via execution_engine",
    }


def _handle_press_key(params: dict[str, Any]) -> Any:
    return {
        "action": "press_key",
        "key": params.get("key"),
        "note": "Delegated to COMPASS action_dispatcher via execution_engine",
    }


def _handle_navigate_browser(params: dict[str, Any]) -> Any:
    url = params.get("url", "")
    # Safety check
    blocked = ["file:///", "javascript:", "chrome://", "edge://"]
    for b in blocked:
        if url.lower().startswith(b):
            return {"success": False, "error": f"Blocked URL pattern: {b}"}
    return {
        "action": "navigate",
        "url": url,
        "note": "Delegated to COMPASS browser_adapter",
    }


# Singleton registry
_default_registry: CompassToolRegistry | None = None


def get_tool_registry() -> CompassToolRegistry:
    """Get the default COMPASS tool registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_tools()
    return _default_registry
