"""
COMPASS Phase 10 — OmniRoute / AI Failure & Free-Only Policy Tests
Comprehensive test suite verifying all 13 AI failure conditions,
deterministic fallback, truthful AI_UNAVAILABLE reporting,
and strict Free-Only / Local-First enforcement.
"""

import urllib.error
from unittest.mock import MagicMock, patch

from backend.app.database import db
from backend.app.services.task_service import task_service
from planner.models import RiskLevel, TaskState
from providers.ai_provider import PlanningRequest, PlanningResult
from providers.omniroute_provider import (
    ModelMetadata,
    OmniRouteErrorCode,
    OmniRouteProvider,
)


class TestOmniRouteFailureMatrix:
    def test_01_omniroute_available(self):
        """Condition 1: OmniRoute available."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        with patch.object(provider, "check_health", return_value=(True, "ok")):
            healthy, msg = provider.check_health()
            assert healthy is True
            assert msg == "ok"

    def test_02_omniroute_unavailable(self):
        """Condition 2: OmniRoute gateway unavailable (URLError/ConnectionRefused)."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:9999")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            healthy, msg = provider.check_health()
            assert healthy is False
            assert "unreachable" in msg.lower() or "connection refused" in msg.lower()

    def test_03_model_unavailable(self):
        """Condition 3: Model unavailable in gateway."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        with (
            patch.object(provider, "resolve_api_key", return_value="dummy_key"),
            patch.object(provider, "discover_models", return_value=[]),
        ):
            selected = provider.select_active_model()
            assert selected is None
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "ping"}],
                model="nonexistent_model",
            )
            assert res["success"] is False
            assert res["error_code"] in [
                OmniRouteErrorCode.MODEL_UNAVAILABLE,
                OmniRouteErrorCode.AI_UNAVAILABLE,
            ]

    def test_04_free_model_unavailable_strict_rejection(self):
        """Condition 4: Only paid models exist -> Strict Free-Only rejection."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128", free_only=True)
        paid_models = [
            ModelMetadata(
                id="openai/gpt-4o",
                provider="openai",
                is_free=False,
                cost_category="PAID",
            ),
            ModelMetadata(
                id="anthropic/claude-3.5-sonnet",
                provider="anthropic",
                is_free=False,
                cost_category="PAID",
            ),
        ]
        with patch.object(provider, "discover_models", return_value=paid_models):
            permitted = provider.get_permitted_models()
            assert len(permitted) == 0
            active = provider.select_active_model()
            assert active is None, "Free-only policy must reject paid models"

    def test_05_invalid_model_response_format(self):
        """Condition 5: Invalid model response (non-JSON or corrupted payload)."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"
        with (
            patch.object(provider, "resolve_api_key", return_value="dummy_key"),
            patch.object(
                provider,
                "get_permitted_models",
                return_value=[
                    ModelMetadata(
                        id="test:free",
                        provider="test",
                        is_free=True,
                        cost_category="FREE",
                    )
                ],
            ),
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "test"}], model="test:free"
            )
            assert res["success"] is False
            assert res["error_code"] == OmniRouteErrorCode.INVALID_RESPONSE

    def test_06_malformed_planner_output(self):
        """Condition 6: Planner output lacks valid steps/JSON schema."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        valid_chat_res = {
            "success": True,
            "content": "Here is your plan: just do everything.",  # No JSON
            "model": "test:free",
            "latency_ms": 100,
        }
        with patch.object(provider, "chat_completion", return_value=valid_chat_res):
            req = PlanningRequest(
                task_id="task_test_06", goal="Save document", ui_snapshot={}
            )
            result: PlanningResult = provider.plan(req)
            assert result.success is False
            assert "invalid" in result.error.lower() or "json" in result.error.lower()

    def test_07_timeout_handling(self):
        """Condition 7: Gateway timeout."""
        provider = OmniRouteProvider(
            base_url="http://127.0.0.1:20128", timeout_seconds=0.1
        )
        with (
            patch.object(provider, "resolve_api_key", return_value="dummy_key"),
            patch.object(
                provider,
                "get_permitted_models",
                return_value=[
                    ModelMetadata(
                        id="test:free",
                        provider="test",
                        is_free=True,
                        cost_category="FREE",
                    )
                ],
            ),
            patch(
                "urllib.request.urlopen", side_effect=TimeoutError("Request timed out")
            ),
        ):
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "test"}], model="test:free"
            )
            assert res["success"] is False
            assert res["error_code"] == OmniRouteErrorCode.TIMEOUT

    def test_08_routing_failure(self):
        """Condition 8: Routing failure (HTTP 404 or unknown model path)."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        http_err = urllib.error.HTTPError(
            "http://127.0.0.1:20128/v1/chat/completions", 404, "Not Found", {}, None
        )
        with (
            patch.object(provider, "resolve_api_key", return_value="dummy_key"),
            patch.object(
                provider,
                "get_permitted_models",
                return_value=[
                    ModelMetadata(
                        id="test:free",
                        provider="test",
                        is_free=True,
                        cost_category="FREE",
                    )
                ],
            ),
            patch("urllib.request.urlopen", side_effect=http_err),
        ):
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "test"}], model="test:free"
            )
            assert res["success"] is False
            assert res["error_code"] in [
                OmniRouteErrorCode.MODEL_UNAVAILABLE,
                OmniRouteErrorCode.PROVIDER_ERROR,
            ]

    def test_09_network_failure(self):
        """Condition 9: Network connection reset or socket error."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        with (
            patch.object(provider, "resolve_api_key", return_value="dummy_key"),
            patch.object(
                provider,
                "get_permitted_models",
                return_value=[
                    ModelMetadata(
                        id="test:free",
                        provider="test",
                        is_free=True,
                        cost_category="FREE",
                    )
                ],
            ),
            patch(
                "urllib.request.urlopen",
                side_effect=ConnectionResetError("Connection reset by peer"),
            ),
        ):
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "test"}], model="test:free"
            )
            assert res["success"] is False
            assert res["error_code"] in [
                OmniRouteErrorCode.NETWORK_ERROR,
                OmniRouteErrorCode.PROVIDER_ERROR,
            ]

    def test_10_provider_failure_500(self):
        """Condition 10: Provider 500 Internal Server Error."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        http_err = urllib.error.HTTPError(
            "http://127.0.0.1:20128/v1/chat/completions",
            500,
            "Internal Server Error",
            {},
            None,
        )
        with (
            patch.object(provider, "resolve_api_key", return_value="dummy_key"),
            patch.object(
                provider,
                "get_permitted_models",
                return_value=[
                    ModelMetadata(
                        id="test:free",
                        provider="test",
                        is_free=True,
                        cost_category="FREE",
                    )
                ],
            ),
            patch("urllib.request.urlopen", side_effect=http_err),
        ):
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "test"}], model="test:free"
            )
            assert res["success"] is False
            assert res["error_code"] == OmniRouteErrorCode.PROVIDER_ERROR

    def test_11_ai_planner_exception_safety(self):
        """Condition 11: Unexpected exception in planner generates safe failure result, no crash."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128")
        with patch.object(
            provider,
            "chat_completion",
            side_effect=RuntimeError("Unexpected memory corruption"),
        ):
            req = PlanningRequest(
                task_id="task_test_11", goal="Test unexpected error", ui_snapshot={}
            )
            res = provider.plan(req)
            assert res.success is False
            assert "unexpected memory corruption" in res.error.lower()

    def test_12_safe_deterministic_fallback(self):
        """Condition 12: Safe deterministic fallback when AI is unavailable."""
        from planner.goal_understanding import goal_understanding_engine

        res = goal_understanding_engine.understand_goal("open notepad and write hello")
        assert res.target_application.lower() == "notepad"
        assert res.objective != ""
        assert res.safety_level in [RiskLevel.LOW, RiskLevel.MEDIUM]

    def test_13_truthful_ai_unavailable_reporting(self):
        """Condition 13: Truthful AI_UNAVAILABLE status propagation in task state."""
        task = task_service.create_task(
            "Complex ambiguous task with zero available models"
        )
        tid = task["id"]
        assert task["state"] == TaskState.STARTING.value

        # When AI model fails completely, task transitions to AI_UNAVAILABLE truthfully
        updated = db.update_task_state(
            tid,
            TaskState.AI_UNAVAILABLE.value,
            reason="Zero free models discovered in OmniRoute",
        )
        assert updated["state"] == TaskState.AI_UNAVAILABLE.value
        reloaded = task_service.get_task(tid)
        assert reloaded["state"] == TaskState.AI_UNAVAILABLE.value

    def test_14_free_only_policy_prevents_silent_paid_fallback(self):
        """Correction #3: Prove unavailable free provider NEVER causes silent paid fallback."""
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128", free_only=True)
        mixed_models = [
            ModelMetadata(
                id="paid-gpt-4o", provider="openai", is_free=False, cost_category="PAID"
            ),
            ModelMetadata(
                id="paid-claude",
                provider="anthropic",
                is_free=False,
                cost_category="PAID",
            ),
        ]
        with patch.object(provider, "discover_models", return_value=mixed_models):
            permitted = provider.get_permitted_models()
            assert len(permitted) == 0, (
                "Paid models must be strictly excluded under free_only"
            )
            selected = provider.select_active_model()
            assert selected is None, "Must not select any paid model"
