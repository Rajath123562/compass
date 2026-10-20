"""
COMPASS OpenRouter Provider (Ponytail Simplified)
Replaces the complex local proxy with a direct OpenRouter API integration.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from providers.ai_provider import (
    AIPlannerProvider,
    PlannedAction,
    PlanningRequest,
    PlanningResult,
)


class OmniRouteErrorCode:
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    CANCELLED = "CANCELLED"


class ModelMetadata:
    def __init__(
        self,
        id: str,
        provider: str = "openrouter",
        is_free: bool = True,
        cost_category: str = "FREE",
        capabilities: list[str] | None = None,
    ):
        self.id = id
        self.provider = provider
        self.is_free = is_free
        self.cost_category = cost_category
        self.context_length = 8192
        self.capabilities = capabilities or ["chat", "vision", "structured_output"]
        self.available = True

    def to_safe_dict(self):
        return self.__dict__


class OmniRouteProvider(AIPlannerProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        free_only: bool = True,
        timeout_seconds: float | None = None,
    ):
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self._base_url = base_url or "https://openrouter.ai/api"
        self._free_only = free_only
        self._cached_models: list[ModelMetadata] | None = None
        self._models_cache_timestamp: float = 0.0
        self._models_cache_ttl: float = 30.0  # 30-second TTL cache for model discovery
        if timeout_seconds is not None:
            self._timeout_seconds = timeout_seconds
        elif os.environ.get("COMPASS_TEST_MODE") == "1" and not self._api_key:
            self._timeout_seconds = float(os.environ.get("COMPASS_LLM_TIMEOUT", "2.0"))
        else:
            self._timeout_seconds = float(os.environ.get("COMPASS_LLM_TIMEOUT", "60.0"))

    @property
    def name(self) -> str:
        return "omniroute"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def free_only(self) -> bool:
        return self._free_only

    def resolve_api_key(self) -> str | None:
        return self._api_key

    def check_health(self) -> tuple[bool, str]:
        # 1. Fast probe local Ollama instance first
        ollama_up = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.04)
                ollama_up = (sock.connect_ex(("127.0.0.1", 11434)) == 0)
        except Exception:
            ollama_up = False

        if ollama_up:
            try:
                req_local = urllib.request.Request(
                    "http://127.0.0.1:11434/api/tags",
                    headers={"User-Agent": "COMPASS-Probe/3.0"},
                )
                with urllib.request.urlopen(req_local, timeout=0.8) as resp:  # nosec B310
                    if resp.status == 200:
                        return True, "Local Ollama Active"
            except Exception:
                pass

        # 2. Probe OpenRouter API endpoint with proper User-Agent
        if not self.base_url.startswith(("http://", "https://")):
            return False, f"Invalid scheme in base_url: {self.base_url}"

        try:
            url = f"{self.base_url}/v1/models" if "/v1" not in self.base_url else self.base_url
            req = urllib.request.Request(url, headers={"User-Agent": "COMPASS-OmniRoute/3.0"})
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:  # noqa: F841  # nosec B310
                pass
            return True, "OpenRouter Integration Active"
        except Exception:
            try:
                req = urllib.request.Request(self.base_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:  # noqa: F841  # nosec B310
                    pass
                return True, "OpenRouter Integration Active"
            except Exception as e:  # noqa: BLE001
                return False, str(e)

    @property
    def is_available(self) -> bool:
        return True

    def is_model_free(self, model_info: Any) -> bool:
        if isinstance(model_info, ModelMetadata):
            return model_info.is_free
        if not model_info:
            return True
        m = str(model_info).strip()
        for meta in self.discover_models():
            if meta.id == m:
                return meta.is_free
        m_lower = m.lower()
        if m_lower.startswith("local/") or m_lower.startswith("ollama/") or ":free" in m_lower:
            return True
        if "gemini" in m_lower and ("flash" in m_lower or "tts" in m_lower or m_lower == "gemini"):
            return True
        if any(p in m_lower for p in ["openai/", "gpt-4", "opus", "sonnet", "paid", "claude-3-haiku", "gemini-pro"]):
            return False
        return False

    def discover_models(self, force_refresh: bool = False) -> list[ModelMetadata]:
        now = time.time()
        if not force_refresh and self._cached_models is not None:
            if (now - self._models_cache_timestamp) < self._models_cache_ttl:
                return list(self._cached_models)

        local_models: list[ModelMetadata] = []

        # 1. Fast socket probe local Ollama instance (http://127.0.0.1:11434)
        ollama_reachable = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.04)
                ollama_reachable = (sock.connect_ex(("127.0.0.1", 11434)) == 0)
        except Exception:
            ollama_reachable = False

        if ollama_reachable:
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/tags",
                    headers={"User-Agent": "COMPASS-Local-Probe"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:  # nosec B310
                    data = json.loads(resp.read().decode("utf-8"))
                    for m in data.get("models", []):
                        name = m.get("name")
                        if name:
                            # Skip embedding-only models
                            if any(non_chat in name.lower() for non_chat in ["bge", "embed", "nomic", "minilm"]):
                                continue
                            local_models.append(
                                ModelMetadata(
                                    id=f"local/ollama/{name}",
                                    provider="ollama",
                                    is_free=True,
                                    cost_category="FREE",
                                    capabilities=["chat", "structured_output", "planning"],
                                )
                            )
            except Exception:  # noqa: BLE001
                pass

        # Sort local models: prioritize lightweight instruction models fitting 4GB VRAM
        def _model_priority(m: ModelMetadata) -> int:
            mid = m.id.lower()
            if "qwen2.5:3b" in mid:
                return 0
            if "coder" in mid:
                return 1
            if "phi-4" in mid:
                return 2
            if "qwen3.5:4b" in mid:
                return 3
            return 4

        local_models.sort(key=_model_priority)

        # 2. Fast socket probe local LM Studio instance (http://localhost:1234)
        lmstudio_reachable = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.04)
                lmstudio_reachable = (sock.connect_ex(("127.0.0.1", 1234)) == 0)
        except Exception:
            lmstudio_reachable = False

        if lmstudio_reachable:
            try:
                req = urllib.request.Request(
                    "http://localhost:1234/v1/models",
                    headers={"User-Agent": "COMPASS-Local-Probe"},
                )
                with urllib.request.urlopen(req, timeout=0.5) as resp:  # nosec B310
                    data = json.loads(resp.read().decode("utf-8"))
                    for m in data.get("data", []):
                        mid = m.get("id")
                        if mid:
                            local_models.append(
                                ModelMetadata(
                                    id=f"local/lmstudio/{mid}",
                                    provider="lmstudio",
                                    is_free=True,
                                    cost_category="FREE",
                                    capabilities=["chat", "structured_output", "planning"],
                                )
                            )
            except Exception:  # noqa: BLE001
                pass

        # Fallback local models if services are offline or returning empty
        if not local_models:
            local_models = [
                ModelMetadata(
                    "local/ollama/qwen2.5:3b-instruct",
                    provider="ollama",
                    is_free=True,
                    cost_category="FREE",
                ),
                ModelMetadata(
                    "local/ollama/qwen2.5-coder:1.5b-instruct",
                    provider="ollama",
                    is_free=True,
                    cost_category="FREE",
                ),
                ModelMetadata(
                    "local/ollama/qwen3.5:4b",
                    provider="ollama",
                    is_free=True,
                    cost_category="FREE",
                ),
            ]

        # Gemini 3.8 Flash models
        gemini_models = [
            ModelMetadata(
                "gemini-3.8-flash",
                provider="gemini",
                is_free=True,
                cost_category="FREE",
                capabilities=["chat", "vision", "computer_use", "planning", "structured_output", "thinking"],
            ),
            ModelMetadata(
                "gemini-2.5-flash",
                provider="gemini",
                is_free=True,
                cost_category="FREE",
                capabilities=["chat", "vision", "planning", "structured_output"],
            ),
        ]

        # Cloud models (only populated if API key is present or for discovery)
        cloud_models = [
            ModelMetadata(
                "claude-opus-5-5",
                provider="anthropic",
                is_free=False,
                cost_category="PAID",
                capabilities=["chat", "vision", "computer_use", "planning", "structured_output"],
            ),
            ModelMetadata(
                "openrouter/nvidia/nemotron-3.5-lightning:free", is_free=True
            ),
            ModelMetadata("openrouter/google/gemini-pro", is_free=False),
            ModelMetadata("openrouter/anthropic/claude-3-haiku", is_free=False),
        ]

        discovered = gemini_models + local_models + cloud_models
        self._cached_models = discovered
        self._models_cache_timestamp = now
        return list(discovered)

    def get_permitted_models(self) -> list[ModelMetadata]:
        models = self.discover_models()
        if self.free_only:
            return [m for m in models if m.is_free]
        return models

    def select_active_model(self) -> str | None:
        models = self.get_permitted_models()
        # If Gemini API Key is configured, prioritize Gemini 3.8 Flash as top AI backbone
        if os.environ.get("GEMINI_API_KEY"):
            for m in models:
                if m.id == "gemini-3.8-flash":
                    return m.id
        # Otherwise prefer local model (e.g. qwen2.5:3b-instruct)
        for m in models:
            if "qwen2.5:3b" in m.id:
                return m.id
        for m in models:
            if m.provider in ("ollama", "lmstudio") or m.id.startswith("local/"):
                return m.id
        return models[0].id if models else None

    def validate_model_capabilities(
        self, model_id: str, required_capabilities: list[str]
    ) -> tuple[bool, str | None]:
        models = self.discover_models()
        model = next((m for m in models if m.id == model_id), None)
        if not model:
            return True, None

        missing = [
            cap for cap in required_capabilities if cap not in model.capabilities
        ]
        if missing:
            return (
                False,
                f"Model {model_id} does not support required capability '{missing[0]}'",
            )

        return True, None

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        response_format: dict[str, str] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        model = model or self.select_active_model()
        if not model:
            model = "local/ollama/qwen2.5:3b-instruct"

        if self._free_only and not self.is_model_free(model):
            return {
                "success": False,
                "error": f"Model '{model}' is blocked by free-only policy [FREE_ONLY]. Only free models or local inference are allowed.",
                "error_code": OmniRouteErrorCode.AI_UNAVAILABLE,
            }

        api_key = self.resolve_api_key()

        # Route to Gemini 3.8 Flash directly
        if model.startswith("gemini") or model in ("gemini-3.8-flash", "gemini-2.5-flash"):
            from providers.gemini_provider import get_gemini_provider

            gp = get_gemini_provider()
            if gp.is_available:
                return gp.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    on_token=on_token,
                )
            else:
                logger.info(
                    "Gemini API key not configured; falling back to local Ollama model."
                )
                model = "local/ollama/qwen2.5:3b-instruct"

        # Route to Claude Opus 5.5 / Anthropic directly
        if model == "claude-opus-5-5" or model.startswith("anthropic/"):
            from providers.claude_computer_use_adapter import ClaudeComputerUseClient
            client = ClaudeComputerUseClient(timeout_seconds=self._timeout_seconds)
            if not client.is_configured:
                return {
                    "success": False,
                    "error": "ANTHROPIC_API_KEY is not configured.",
                    "error_code": OmniRouteErrorCode.AUTHENTICATION_FAILED,
                }
            system_prompt = next((m.get("content", "") for m in messages if m.get("role") == "system"), "You are COMPASS assistant.")
            api_msgs = []
            for m in messages:
                if m.get("role") != "system":
                    api_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
            if not api_msgs:
                api_msgs = [{"role": "user", "content": "Hello"}]
            resp = client.send_turn(messages=api_msgs, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens)
            if resp.get("success"):
                content = "".join([b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text"])
                if on_token and content:
                    on_token(content)
                return {"success": True, "content": content}
            else:
                return {
                    "success": False,
                    "error": resp.get("error", "Claude API request failed"),
                    "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
                }

        # Route to LM Studio if specified
        if model.startswith("local/lmstudio/"):
            lm_model = model.replace("local/lmstudio/", "")
            should_stream = on_token is not None
            payload = {
                "model": lm_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": should_stream,
            }
            if response_format and response_format.get("type") == "json_object":
                payload["response_format"] = {"type": "json_object"}
            req = urllib.request.Request(
                "http://localhost:1234/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:  # nosec B310
                    if not should_stream:
                        data = json.loads(resp.read().decode("utf-8"))
                        content = data["choices"][0]["message"]["content"]
                        return {"success": True, "content": content}
                    else:
                        full_content = []
                        for line in resp:
                            line_str = line.decode("utf-8").strip()
                            if not line_str or line_str == "data: [DONE]":
                                continue
                            line_str = line_str.removeprefix("data: ")
                            try:
                                chunk_data = json.loads(line_str)
                                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                                chunk_content = delta.get("content", "")
                                if chunk_content:
                                    full_content.append(chunk_content)
                                    if on_token:
                                        on_token(chunk_content)
                            except Exception:
                                continue
                        return {"success": True, "content": "".join(full_content)}
            except Exception as e:  # noqa: BLE001
                return {
                    "success": False,
                    "error": f"LM Studio integration failed: {e!s}",
                    "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
                }

        # Check if local Ollama routing should handle this request
        is_ollama = (
            model.startswith("local/ollama/")
            or model.startswith("ollama/")
            or "qwen" in model.lower()
            or not api_key
        )

        if is_ollama:
            ollama_reachable = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.05)
                    ollama_reachable = (sock.connect_ex(("127.0.0.1", 11434)) == 0)
            except Exception:
                ollama_reachable = False

            if not ollama_reachable:
                return {
                    "success": False,
                    "error": "Local Ollama service (127.0.0.1:11434) is not running.",
                    "error_code": OmniRouteErrorCode.AI_UNAVAILABLE,
                }

            ollama_model = (
                model.replace("local/ollama/", "").replace("ollama/", "")
            )
            # Find actually installed local models from Ollama
            installed_models = []
            try:
                for m in self.discover_models():
                    if m.provider == "ollama" and m.id.startswith("local/ollama/"):
                        installed_models.append(m.id.replace("local/ollama/", ""))
            except Exception:
                pass

            # Build prioritized list of candidate models to try: requested model first, then installed models
            candidate_models = []
            if ollama_model and not ollama_model.startswith("openrouter/"):
                candidate_models.append(ollama_model)
            for m in installed_models:
                if m not in candidate_models:
                    candidate_models.append(m)
            if not candidate_models:
                candidate_models = ["qwen2.5:3b-instruct", "qwen3.5:4b", "gemma4:e4b"]

            should_stream = on_token is not None
            last_err = None

            for try_model in candidate_models:
                options = {"temperature": temperature}
                if max_tokens:
                    options["num_predict"] = max_tokens
                ollama_payload = {
                    "model": try_model,
                    "messages": messages,
                    "stream": should_stream,
                    "options": options,
                }
                if response_format and response_format.get("type") == "json_object":
                    ollama_payload["format"] = "json"

                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=json.dumps(ollama_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                try:
                    with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:  # nosec B310
                        if not should_stream:
                            data = json.loads(resp.read().decode("utf-8"))
                            msg_obj = data.get("message", {})
                            content = (
                                msg_obj.get("content")
                                or msg_obj.get("thinking")
                                or msg_obj.get("reasoning_content")
                                or ""
                            )
                            return {"success": True, "content": content}
                        else:
                            full_content = []
                            for line in resp:
                                line_str = line.decode("utf-8").strip()
                                if not line_str:
                                    continue
                                try:
                                    chunk_data = json.loads(line_str)
                                    chunk_msg = chunk_data.get("message", {})
                                    chunk_content = (
                                        chunk_msg.get("content")
                                        or chunk_msg.get("thinking")
                                        or chunk_msg.get("reasoning_content")
                                        or ""
                                    )
                                    if chunk_content:
                                        full_content.append(chunk_content)
                                        if on_token:
                                            on_token(chunk_content)
                                    if chunk_data.get("done", False):
                                        break
                                except Exception:
                                    continue
                            return {"success": True, "content": "".join(full_content)}
                except urllib.error.HTTPError as e:
                    last_err = e
                    if e.code == 404:
                        # Model not found on Ollama, try next installed model
                        continue
                    return {
                        "success": False,
                        "error": f"Ollama integration failed: {e!s}",
                        "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
                    }
                except Exception as e:
                    last_err = e
                    return {
                        "success": False,
                        "error": f"Ollama integration failed: {e!s}",
                        "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
                    }

            return {
                "success": False,
                "error": f"Ollama integration failed: {last_err or 'No compatible model found'}",
                "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
            }

        # Fallback to OpenRouter for cloud models
        if not api_key:
            return {
                "success": False,
                "error": "No OPENROUTER_API_KEY for cloud models",
                "error_code": OmniRouteErrorCode.AUTHENTICATION_FAILED,
            }

        if self.free_only and "free" not in model:
            return {
                "success": False,
                "error": "FREE_ONLY policy violation",
                "error_code": OmniRouteErrorCode.AI_UNAVAILABLE,
            }

        # Strip openrouter/ prefix - OpenRouter API expects bare model names
        api_model = model
        api_model = api_model.removeprefix("openrouter/")

        payload = {
            "model": api_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        import time
        max_retries = 3
        for attempt in range(max_retries):
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:  # nosec B310
                    data = json.loads(resp.read().decode("utf-8"))
                    return {
                        "success": True,
                        "content": data["choices"][0]["message"]["content"],
                    }
            except urllib.error.HTTPError as e:
                if e.code in [429, 502, 503] and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                if e.code == 429:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_code": OmniRouteErrorCode.RATE_LIMITED,
                    }
                return {
                    "success": False,
                    "error": str(e),
                    "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
                }
            except TimeoutError:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {
                    "success": False,
                    "error": "Timeout",
                    "error_code": OmniRouteErrorCode.TIMEOUT,
                }
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": str(e),
                    "error_code": OmniRouteErrorCode.INVALID_RESPONSE,
                }
            except Exception as e:  # noqa: BLE001
                return {
                    "success": False,
                    "error": str(e),
                    "error_code": OmniRouteErrorCode.PROVIDER_ERROR,
                }

    def plan(self, request: PlanningRequest) -> PlanningResult:
        messages = [
            {
                "role": "system",
                "content": "You are a UI planner. Respond in JSON with a 'steps' array. Each step MUST have 'action_type' and 'target_ref'.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"goal": request.goal, "ui_snapshot": request.ui_snapshot}
                ),
            },
        ]
        try:
            resp = self.chat_completion(messages=messages)
        except json.JSONDecodeError as e:
            return PlanningResult(
                success=False, goal=request.goal, error=f"Invalid JSON: {e!s}"
            )
        except Exception as e:  # noqa: BLE001
            return PlanningResult(success=False, goal=request.goal, error=str(e))

        if not resp["success"]:
            return PlanningResult(success=False, goal=request.goal, error=resp["error"])

        try:
            data = json.loads(resp["content"])
            actions = [
                PlannedAction(
                    action_type=s.get("action_type", "click"),
                    target_ref=s.get("target_ref", {}),
                    target_description=s.get("target_description", "UI element"),
                    expected_result=s.get("expected_result", "Action completed"),
                )
                for s in data.get("steps", [])
            ]
            return PlanningResult(
                success=True, goal=request.goal, planned_actions=actions
            )
        except json.JSONDecodeError as e:
            return PlanningResult(
                success=False, goal=request.goal, error=f"Invalid JSON: {e!s}"
            )
        except Exception as e:  # noqa: BLE001
            return PlanningResult(success=False, goal=request.goal, error=str(e))
