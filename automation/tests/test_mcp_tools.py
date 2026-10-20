"""
COMPASS — MCP Tool Interface Tests
Tests for automation/mcp_tools.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from automation.mcp_tools import (
    CompassToolRegistry,
    ToolPermission,
    ToolSchema,
    create_default_tools,
    get_tool_registry,
)


class TestCompassToolRegistry:
    def test_register_and_list(self):
        registry = CompassToolRegistry()
        schema = ToolSchema(
            name="test_tool", description="A test tool", permission=ToolPermission.READ
        )

        def handler(params):
            return {"ok": True}

        registry.register(schema, handler)
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"

    def test_invoke_valid_tool(self):
        registry = CompassToolRegistry()
        registry.register(
            ToolSchema("test", "test", ToolPermission.READ),
            lambda p: {"result": "success"},
        )
        res = registry.invoke("test", {})
        assert res.success is True
        assert res.data == {"result": "success"}

    def test_invoke_unknown_tool(self):
        registry = CompassToolRegistry()
        res = registry.invoke("unknown", {})
        assert res.success is False
        assert "Unknown tool" in res.error

    def test_parameter_validation_missing_required(self):
        registry = CompassToolRegistry()
        schema = ToolSchema(
            name="test",
            description="test",
            permission=ToolPermission.WRITE,
            parameters={
                "type": "object",
                "properties": {"arg1": {"type": "string"}},
                "required": ["arg1"],
            },
        )
        registry.register(schema, lambda p: {})
        res = registry.invoke("test", {})
        assert res.success is False
        assert "Missing required parameter" in res.error

    def test_parameter_validation_wrong_type(self):
        registry = CompassToolRegistry()
        schema = ToolSchema(
            name="test",
            description="test",
            permission=ToolPermission.WRITE,
            parameters={
                "type": "object",
                "properties": {"arg1": {"type": "string"}},
            },
        )
        registry.register(schema, lambda p: {})
        res = registry.invoke("test", {"arg1": 123})
        assert res.success is False
        assert "must be a string" in res.error

    def test_invocation_logging(self):
        registry = CompassToolRegistry()
        registry.register(ToolSchema("test", "test", ToolPermission.READ), lambda p: {})
        registry.invoke("test", {})
        logs = registry.get_invocation_log()
        assert len(logs) == 1
        assert logs[0]["tool"] == "test"
        assert logs[0]["success"] is True


class TestDefaultTools:
    def test_create_default_tools(self):
        registry = create_default_tools()
        tools = registry.list_tools()
        # Should have 11 default tools
        assert len(tools) == 11
        names = [t["name"] for t in tools]
        assert "inspect_ui" in names
        assert "click_element" in names
        assert "navigate_browser" in names

    def test_get_tool_registry_singleton(self):
        r1 = get_tool_registry()
        r2 = get_tool_registry()
        assert r1 is r2

    @patch("perception.uia_inspector.get_foreground_window")
    def test_inspect_ui_no_window(self, mock_get_window):
        mock_get_window.return_value = None
        registry = create_default_tools()
        res = registry.invoke("inspect_ui", {})
        assert res.success is True  # The handler itself didn't crash
        assert res.data["error"] == "No foreground window"
