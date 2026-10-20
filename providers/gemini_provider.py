"""
COMPASS Gemini Provider
Full-featured Gemini 3.8 Flash AI backbone implementation using google-genai SDK.
Supports Thinking Mode, Function Calling, Streaming, Planning, and Token Budget Management.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from backend.app.logging_config import logger
from providers.ai_provider import (
    AIPlannerProvider,
    PlannedAction,
    PlanningRequest,
    PlanningResult,
)
from providers.gemini_tools import COMPASS_CALLABLE_TOOLS, execute_tool_call
from providers.token_budget import get_token_budget_manager

DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-2.5-flash"


class GeminiProvider(AIPlannerProvider):
    """
    Primary AI provider for COMPASS, powered by Google Gemini 3.8 Flash.
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = DEFAULT_MODEL,
        thinking_budget: int = 1024,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.default_model = default_model
        self.thinking_budget = thinking_budget
        self.timeout_seconds = timeout_seconds
        self._client = None
        self._token_budget = get_token_budget_manager()

        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the google-genai client."""
        try:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        except Exception as e:
            logger.error(f"Failed to initialize google-genai client: {e}")
            self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key and self._client is not None)

    @property
    def budget_manager(self) -> TokenBudgetManager:
        return self._token_budget

    def get_budget_metrics(self) -> dict[str, Any]:
        return self._token_budget.get_metrics()

    def set_api_key(self, api_key: str) -> None:
        """Set or update the Gemini API key at runtime."""
        self._api_key = api_key
        os.environ["GEMINI_API_KEY"] = api_key
        self._init_client()

    def check_health(self) -> tuple[bool, str]:
        """Verify API key validity and connectivity to Gemini service."""
        if not self._api_key:
            return False, "GEMINI_API_KEY environment variable is not configured."
        if not self._client:
            self._init_client()
            if not self._client:
                return False, "Failed to initialize google-genai SDK client."

        can_run, budget_err = self._token_budget.can_execute()
        if not can_run:
            return False, budget_err or "Token budget limit reached."

        try:
            # Lightweight probe
            resp = self._client.models.generate_content(
                model=self.default_model,
                contents="ping",
            )
            if resp and resp.text:
                return True, f"Gemini 3.8 Flash Active ({self.default_model})"
            return True, "Gemini Connected"
        except Exception as e:
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                return False, "Gemini API rate limit reached (RPM/TPM limit)."
            if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str or "403" in err_str:
                return False, "Gemini API key is invalid or lacks required permissions."
            return False, f"Gemini connection error: {err_str}"

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        thinking_budget: int | None = None,
        on_token: Callable[[str], None] | None = None,
        tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a conversational response, optionally with streaming and thinking mode.
        """
        start_time = time.time()
        target_model = model or self.default_model

        if not self.is_available:
            return {
                "success": False,
                "error": "Gemini API key not configured. Set GEMINI_API_KEY.",
                "error_code": "AUTHENTICATION_FAILED",
                "latency_ms": 0.0,
            }

        can_run, budget_err = self._token_budget.can_execute()
        if not can_run:
            return {
                "success": False,
                "error": budget_err or "Token budget exceeded",
                "error_code": "RATE_LIMITED",
                "latency_ms": 0.0,
            }

        try:
            from google.genai import types

            # Format contents from message sequence
            system_instruction = None
            contents: list[types.Content] = []

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    system_instruction = content
                elif role in ("assistant", "model"):
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=content)],
                        )
                    )
                else:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=content)],
                        )
                    )

            # Build config
            config_kwargs: dict[str, Any] = {
                "temperature": temperature,
            }
            if max_tokens:
                config_kwargs["max_output_tokens"] = max_tokens
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            # Configure thinking mode if supported/specified
            effective_thinking = (
                thinking_budget if thinking_budget is not None else self.thinking_budget
            )
            if effective_thinking and effective_thinking > 0:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=effective_thinking
                )

            # Configure function calling tools if provided
            if tools:
                config_kwargs["tools"] = tools

            config = types.GenerateContentConfig(**config_kwargs)

            # Streaming mode if on_token provided
            if on_token:
                full_text = []
                response_stream = self._client.models.generate_content_stream(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
                for chunk in response_stream:
                    chunk_text = chunk.text or ""
                    if chunk_text:
                        full_text.append(chunk_text)
                        on_token(chunk_text)

                combined_content = "".join(full_text)
                latency = round((time.time() - start_time) * 1000, 2)

                # Track token usage estimate
                self._token_budget.record_usage(
                    model=target_model,
                    prompt_tokens=len(str(messages)) // 4,
                    completion_tokens=len(combined_content) // 4,
                )

                return {
                    "success": True,
                    "content": combined_content,
                    "model": target_model,
                    "latency_ms": latency,
                }
            else:
                response = self._client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )

                latency = round((time.time() - start_time) * 1000, 2)
                content = response.text or ""

                # Extract tool calls if returned
                tool_calls = []
                if response.function_calls:
                    for fc in response.function_calls:
                        tool_calls.append(
                            {
                                "name": fc.name,
                                "args": dict(fc.args) if fc.args else {},
                            }
                        )

                # Record usage telemetry
                prompt_tok = 0
                resp_tok = 0
                if getattr(response, "usage_metadata", None):
                    prompt_tok = response.usage_metadata.prompt_token_count or 0
                    resp_tok = response.usage_metadata.candidates_token_count or 0
                else:
                    prompt_tok = len(str(messages)) // 4
                    resp_tok = len(content) // 4

                self._token_budget.record_usage(
                    model=target_model,
                    prompt_tokens=prompt_tok,
                    completion_tokens=resp_tok,
                )

                return {
                    "success": True,
                    "content": content,
                    "model": target_model,
                    "tool_calls": tool_calls,
                    "latency_ms": latency,
                }

        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            err_msg = str(e)
            logger.error(f"Gemini API request error: {err_msg}")
            return {
                "success": False,
                "error": err_msg,
                "error_code": "PROVIDER_ERROR",
                "latency_ms": latency,
            }

    def plan(self, request: PlanningRequest) -> PlanningResult:
        """
        Generate a structured action plan for the given goal and UI state.
        Uses Gemini function calling or structured JSON output.
        """
        start = time.time()
        if not self.is_available:
            return PlanningResult(
                success=False,
                goal=request.goal,
                error="Gemini API is not configured",
                model_used=self.default_model,
                latency_ms=0.0,
            )

        system_prompt = (
            "You are COMPASS, an autonomous AI interface assistant for Windows.\n"
            "Given a user goal and current UI elements, choose the precise action sequence to achieve it.\n"
            "Available actions: launch_app, open_website, click_ui_element, type_into_element, press_keyboard_key, scroll_screen."
        )

        elements_summary = []
        for el in request.ui_snapshot.get("elements", [])[:30]:
            elements_summary.append(
                f"- Name: '{el.get('name')}', Control: {el.get('control_type')}, Bounds: {el.get('bounds')}"
            )

        user_content = (
            f"Goal: {request.goal}\n"
            f"Active Window: {request.ui_snapshot.get('window', {}).get('title', 'Unknown')}\n"
            f"Visible Elements:\n" + "\n".join(elements_summary)
        )

        resp = self.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=self.default_model,
            tools=COMPASS_CALLABLE_TOOLS,
        )

        latency = round((time.time() - start) * 1000, 2)

        if not resp.get("success"):
            return PlanningResult(
                success=False,
                goal=request.goal,
                error=resp.get("error", "AI Planning failed"),
                model_used=self.default_model,
                latency_ms=latency,
            )

        tool_calls = resp.get("tool_calls", [])
        planned_actions: list[PlannedAction] = []

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {})
            action_type = "click"
            if name == "launch_app":
                action_type = "launch_app"
            elif name == "open_website":
                action_type = "open_url"
            elif name == "type_into_element":
                action_type = "type"
            elif name == "press_keyboard_key":
                action_type = "key"
            elif name == "scroll_screen":
                action_type = "scroll"

            planned_actions.append(
                PlannedAction(
                    action_type=action_type,
                    target_ref={"name": args.get("description", args.get("app_name", ""))},
                    parameters=args,
                    rationale=f"Executing tool {name}",
                )
            )

        return PlanningResult(
            success=True,
            goal=request.goal,
            planned_actions=planned_actions,
            model_used=self.default_model,
            latency_ms=latency,
        )


# Global singleton instance
_gemini_provider_instance: GeminiProvider | None = None


def get_gemini_provider() -> GeminiProvider:
    global _gemini_provider_instance
    if _gemini_provider_instance is None:
        _gemini_provider_instance = GeminiProvider()
    return _gemini_provider_instance
