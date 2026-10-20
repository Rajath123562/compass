"""
Unit tests for OmniRoute Provider and Free-Only Policy.
"""

from unittest.mock import MagicMock, patch

from providers.omniroute_provider import (
    ModelMetadata,
    OmniRouteErrorCode,
    OmniRouteProvider,
)


class TestOmniRouteProvider:
    def test_provider_initialization(self):
        provider = OmniRouteProvider(base_url="http://127.0.0.1:20128", free_only=True)
        assert provider.name == "omniroute"
        assert provider.base_url == "http://127.0.0.1:20128"
        assert provider.free_only is True

    def test_resolve_api_key_override(self):
        provider = OmniRouteProvider(api_key="test-key-12345")
        assert provider.resolve_api_key() == "test-key-12345"

    def test_free_only_policy_enforcement(self):
        provider = OmniRouteProvider(api_key="mock-key", free_only=True)

        # Mock discovered models with a mix of free and paid
        mock_models = [
            ModelMetadata(
                id="test/free-model:free",
                provider="test",
                is_free=True,
                cost_category="FREE",
            ),
            ModelMetadata(
                id="test/paid-model",
                provider="test",
                is_free=False,
                cost_category="PAID",
            ),
            ModelMetadata(
                id="test/unknown-model",
                provider="test",
                is_free=False,
                cost_category="UNKNOWN_COST",
            ),
        ]

        with patch.object(provider, "discover_models", return_value=mock_models):
            permitted = provider.get_permitted_models()
            assert len(permitted) == 1
            assert permitted[0].id == "test/free-model:free"

            # Attempting to call chat_completion with paid model must be blocked immediately
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "hi"}], model="test/paid-model"
            )
            assert res["success"] is False
            assert res["error_code"] == OmniRouteErrorCode.AI_UNAVAILABLE
            assert "FREE_ONLY" in res["error"]

    def test_error_classification_rate_limit(self):
        provider = OmniRouteProvider(api_key="mock-key", free_only=False)
        with patch.object(
            provider,
            "get_permitted_models",
            return_value=[
                ModelMetadata(
                    id="test-model", provider="test", is_free=True, cost_category="FREE"
                )
            ],
        ):
            import urllib.error

            mock_error = urllib.error.HTTPError(
                url="http://mock",
                code=429,
                msg="Too Many Requests",
                hdrs={},
                fp=MagicMock(read=lambda: b"Quota exceeded"),
            )
            with patch("urllib.request.urlopen", side_effect=mock_error):
                res = provider.chat_completion(
                    messages=[{"role": "user", "content": "hi"}], model="test-model"
                )
                assert res["success"] is False
                assert res["error_code"] == OmniRouteErrorCode.RATE_LIMITED

    def test_error_classification_timeout(self):
        provider = OmniRouteProvider(api_key="mock-key", free_only=False)
        with patch.object(
            provider,
            "get_permitted_models",
            return_value=[
                ModelMetadata(
                    id="test-model", provider="test", is_free=True, cost_category="FREE"
                )
            ],
        ), patch(
            "urllib.request.urlopen", side_effect=TimeoutError("Request timed out")
        ):
            res = provider.chat_completion(
                messages=[{"role": "user", "content": "hi"}], model="test-model"
            )
            assert res["success"] is False
            assert res["error_code"] == OmniRouteErrorCode.TIMEOUT

    def test_validate_model_capabilities_enforced(self):
        """Directive §25: Capabilities must be checked before relying on model."""
        provider = OmniRouteProvider(api_key="mock-key", free_only=False)
        mock_models = [
            ModelMetadata(
                id="chat-only-model",
                provider="test",
                is_free=True,
                cost_category="FREE",
                capabilities=["chat"],
            ),
            ModelMetadata(
                id="multimodal-model",
                provider="test",
                is_free=True,
                cost_category="FREE",
                capabilities=["chat", "vision"],
            ),
        ]
        with patch.object(provider, "discover_models", return_value=mock_models):
            # Checking chat capability on chat model passes
            ok, err = provider.validate_model_capabilities("chat-only-model", ["chat"])
            assert ok is True
            assert err is None

            # Checking vision capability on chat-only model fails
            ok, err = provider.validate_model_capabilities(
                "chat-only-model", ["vision"]
            )
            assert ok is False
            assert "does not support required capability 'vision'" in err

            # Checking vision capability on multimodal model passes
            ok, err = provider.validate_model_capabilities(
                "multimodal-model", ["vision"]
            )
            assert ok is True
            assert err is None
