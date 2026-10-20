"""
Unit tests for Phase 3: Universal Execution Tiering & Live Token Streaming.
"""

from unittest.mock import MagicMock, patch

from providers.hardware_detector import get_execution_tier, get_system_hardware
from providers.omniroute_provider import OmniRouteProvider


def test_execution_tier_tier1_gpu():
    mock_hw = {
        "os": "Windows",
        "ram_total_mb": 12288.0,
        "gpus": [
            {"name": "NVIDIA GeForce RTX 2050", "vram_mb": 4096.0}
        ],
    }
    tier_info = get_execution_tier(mock_hw)
    assert tier_info["tier"] == 1
    assert "3b-instruct" in tier_info["recommended_model"]
    assert tier_info["vram_ceiling_mb"] == 2500
    assert tier_info["device"] == "cuda"


def test_execution_tier_tier2_hybrid_igpu():
    mock_hw = {
        "os": "Windows",
        "ram_total_mb": 16384.0,
        "gpus": [
            {"name": "Intel(R) UHD Graphics", "vram_mb": 128.0}
        ],
    }
    tier_info = get_execution_tier(mock_hw)
    assert tier_info["tier"] == 2
    assert "1.5b-instruct" in tier_info["recommended_model"]
    assert tier_info["device"] == "hybrid"


def test_execution_tier_tier3_cpu_quantized():
    mock_hw = {
        "os": "Windows",
        "ram_total_mb": 4096.0,
        "gpus": [],
    }
    tier_info = get_execution_tier(mock_hw)
    assert tier_info["tier"] == 3
    assert "0.5b" in tier_info["recommended_model"]
    assert tier_info["device"] == "cpu"
    assert tier_info["vram_ceiling_mb"] == 0


def test_get_system_hardware_includes_execution_tier():
    hw = get_system_hardware()
    assert "execution_tier" in hw
    assert hw["execution_tier"]["tier"] in (1, 2, 3)
    assert "recommended_model" in hw["execution_tier"]


def test_chat_completion_with_on_token_streaming():
    provider = OmniRouteProvider(free_only=False)

    lines = [
        b'{"message": {"content": "Hello"}, "done": false}\n',
        b'{"message": {"content": " world"}, "done": false}\n',
        b'{"message": {"content": "!"}, "done": true}\n',
    ]

    mock_resp = MagicMock()
    mock_resp.__iter__.return_value = iter(lines)
    mock_resp.__enter__.return_value = mock_resp

    tokens_received = []

    def handle_token(token: str):
        tokens_received.append(token)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="local/ollama/qwen2.5:3b-instruct",
            on_token=handle_token,
        )

    assert res["success"] is True
    assert res["content"] == "Hello world!"
    assert tokens_received == ["Hello", " world", "!"]
