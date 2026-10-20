"""
Unit tests for Phase 2: Gemini 3.8 Flash Provider and Smart Token Budget.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from providers.ai_provider import PlanningRequest
from providers.gemini_provider import GeminiProvider, get_gemini_provider
from providers.gemini_tools import (
    COMPASS_CALLABLE_TOOLS,
    execute_tool_call,
    launch_app,
    open_website,
)
from providers.omniroute_provider import OmniRouteProvider
from providers.token_budget import TokenBudgetManager, get_token_budget_manager


class TestTokenBudgetManager:
    """Test token budget limits, cost calculation, and warning triggers."""

    def test_record_usage_and_metrics(self):
        manager = TokenBudgetManager(daily_token_limit=10000, daily_request_limit=50)
        manager.reset()

        cost = manager.record_usage("gemini-3.8-flash", prompt_tokens=1000, completion_tokens=500)
        metrics = manager.get_metrics()

        assert metrics["total_requests"] == 1
        assert metrics["total_prompt_tokens"] == 1000
        assert metrics["total_completion_tokens"] == 500
        assert metrics["total_tokens"] == 1500
        assert metrics["is_warning_level"] is False
        assert metrics["remaining_daily_tokens"] == 8500

    def test_warning_threshold_exceeded(self):
        manager = TokenBudgetManager(daily_token_limit=1000, warning_threshold_ratio=0.8)
        manager.reset()

        manager.record_usage("gemini-3.8-flash", prompt_tokens=600, completion_tokens=250)
        metrics = manager.get_metrics()
        assert metrics["is_warning_level"] is True

    def test_can_execute_enforces_limits(self):
        manager = TokenBudgetManager(daily_token_limit=500, daily_request_limit=2)
        manager.reset()

        can_run, _ = manager.can_execute()
        assert can_run is True

        manager.record_usage("gemini-3.8-flash", 300, 300)
        can_run, err = manager.can_execute()
        assert can_run is False
        assert "Daily token budget exceeded" in err


class TestGeminiTools:
    """Test function calling tools defined for Gemini."""

    def test_callable_tools_count(self):
        assert len(COMPASS_CALLABLE_TOOLS) >= 8

    @patch("automation.action_dispatcher.launch_application")
    def test_launch_app_tool(self, mock_launch):
        mock_launch.return_value = MagicMock(to_dict=lambda: {"success": True, "action": "launch_app"})
        res_str = launch_app("calc")
        data = json.loads(res_str)
        assert data.get("success") is True

    @patch("automation.action_dispatcher.open_url")
    def test_open_website_tool(self, mock_open_url):
        mock_open_url.return_value = MagicMock(to_dict=lambda: {"success": True, "action": "open_url"})
        res_str = open_website("https://google.com")
        data = json.loads(res_str)
        assert data.get("success") is True

    def test_execute_unknown_tool(self):
        res = execute_tool_call("non_existent_tool_123", {})
        data = json.loads(res)
        assert "error" in data


class TestGeminiProvider:
    """Test GeminiProvider integration with mocked google-genai SDK."""

    def test_provider_initialization_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            p = GeminiProvider(api_key=None)
            assert p.is_available is False
            health_ok, reason = p.check_health()
            assert health_ok is False
            assert "GEMINI_API_KEY" in reason

    @patch("google.genai.Client")
    def test_provider_with_api_key(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GeminiProvider(api_key="test_dummy_key_123")
        assert provider.is_available is True
        assert provider.name == "gemini"

    @patch("google.genai.Client")
    def test_chat_completion_mock(self, mock_client_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini 3.8 Flash!"
        mock_response.function_calls = None
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 10
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GeminiProvider(api_key="test_dummy_key_123")
        res = provider.chat_completion(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gemini-3.8-flash",
        )
        assert res.get("success") is True
        assert res.get("content") == "Hello from Gemini 3.8 Flash!"
        assert res.get("model") == "gemini-3.8-flash"

    @patch("google.genai.Client")
    def test_chat_completion_streaming_mock(self, mock_client_class):
        mock_client = MagicMock()
        chunk1 = MagicMock(text="Hello ")
        chunk2 = MagicMock(text="World!")
        mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]
        mock_client_class.return_value = mock_client

        tokens_received = []

        def token_callback(token: str):
            tokens_received.append(token)

        provider = GeminiProvider(api_key="test_dummy_key_123")
        res = provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            on_token=token_callback,
        )
        assert res.get("success") is True
        assert res.get("content") == "Hello World!"
        assert tokens_received == ["Hello ", "World!"]

    @patch("google.genai.Client")
    def test_plan_with_function_calling_mock(self, mock_client_class):
        mock_client = MagicMock()
        mock_fc = MagicMock()
        mock_fc.name = "launch_app"
        mock_fc.args = {"app_name": "notepad"}

        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.function_calls = [mock_fc]
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 20
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GeminiProvider(api_key="test_dummy_key_123")
        req = PlanningRequest(
            goal="Open Notepad",
            ui_snapshot={"window": {"title": "Desktop"}, "elements": []},
        )
        plan_res = provider.plan(req)
        assert plan_res.success is True
        assert len(plan_res.planned_actions) == 1
        assert plan_res.planned_actions[0].action_type == "launch_app"


class TestOmniRouteGeminiIntegration:
    """Test OmniRouteProvider model discovery and Gemini routing."""

    def test_discover_models_contains_gemini(self):
        omni = OmniRouteProvider()
        models = omni.discover_models(force_refresh=True)
        model_ids = [m.id for m in models]
        assert "gemini-3.8-flash" in model_ids
        assert "gemini-2.5-flash" in model_ids

    def test_is_model_free_for_gemini(self):
        omni = OmniRouteProvider()
        assert omni.is_model_free("gemini-3.8-flash") is True
        assert omni.is_model_free("gemini-2.5-flash") is True

    @patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_gemini_key"})
    def test_select_active_model_prioritizes_gemini(self):
        omni = OmniRouteProvider()
        active = omni.select_active_model()
        assert active == "gemini-3.8-flash"
