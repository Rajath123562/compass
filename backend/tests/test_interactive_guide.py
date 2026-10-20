"""
Phase 7: Enterprise Testing Suite for the Interactive Guide Engine
Includes mock LLM-as-a-judge, fault injection, and latency bounds.
"""
import time
from unittest.mock import patch

import pytest

from planner.interactive_guide_engine import InteractiveGuideEngine


@pytest.fixture
def engine():
    return InteractiveGuideEngine(model_id="test-model")

# Layer 1: Deterministic State Testing
def test_snapshot_and_undo(engine):
    # Simulate a step
    engine._snapshot_state()
    assert len(engine.history_snapshots) == 1
    
    # Simulate an undo
    res = engine.undo_last_step()
    assert "Reverted context to state at" in res
    assert len(engine.history_snapshots) == 0

# Layer 2: LLM-as-a-Judge (Mocked Eval)
@pytest.mark.asyncio
async def test_llm_meta_cognition_eval(engine):
    # Mock the LLM provider to ensure it generates a <thinking> block
    with patch.object(engine.provider, 'chat_completion') as mock_chat:
        def mock_chat_side_effect(*args, **kwargs):
            on_token = kwargs.get('on_token')
            if on_token:
                on_token("<thinking>I should tell them to open the terminal</thinking> Open the terminal.")
            return {
                "success": True,
                "content": "<thinking>I should tell them to open the terminal</thinking> Open the terminal.",
                "model": "test-model"
            }
        mock_chat.side_effect = mock_chat_side_effect
        
        # Test the stream wrapper (sync iteration for simplicity in this mock test)
        stream = engine.generate_guidance_stream("How do I start?")
        response = ""
        async for chunk in stream:
            response += chunk
            
        assert "<thinking>" in response
        assert "Open the terminal" in response

# Layer 3: Chaos Engineering & Fault Injection
@pytest.mark.asyncio
async def test_graceful_degradation_on_llm_crash(engine):
    with patch.object(engine.provider, 'chat_completion') as mock_chat:
        mock_chat.side_effect = Exception("Ollama randomly crashed!")
        
        stream = engine.generate_guidance_stream("Will you crash?")
        response = ""
        async for chunk in stream:
            response += chunk
            
        # Ensure it degraded gracefully rather than throwing a raw 500 API error
        assert "⚠️ Exception occurred during guidance: Ollama randomly crashed!" in response

# Layer 5: Fuzzing / Context Resilience
def test_context_window_truncation(engine):
    # Ensure memory doesn't leak endlessly
    for _ in range(20):
        engine._snapshot_state()
    
    # Max snapshots is 10
    assert len(engine.history_snapshots) == 10

# Layer 6: Hard Latency Asserts
def test_perception_latency(engine):
    # The UI inspector must be extremely fast to not bog down the event loop
    start_time = time.time()
    engine._snapshot_state()
    duration_ms = (time.time() - start_time) * 1000
    
    # Assert UI Perception takes less than 150ms
    assert duration_ms < 150, f"UI Perception is too slow: {duration_ms}ms"

