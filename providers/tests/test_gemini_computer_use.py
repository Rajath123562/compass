"""
Unit tests for Gemini Native Computer Use Agent.
"""

from unittest.mock import MagicMock, patch

import pytest

from perception.screen_capture import ScreenSnapshot
from providers.gemini_computer_use import (
    ComputerAction,
    GeminiComputerUse,
)


class TestGeminiComputerUse:
    """Test Computer Use loop, coordinate mapping, safety checking, and action dispatch."""

    @patch("perception.screen_capture.ScreenCapture.capture_screen")
    def test_offline_heuristic_fallback(self, mock_capture):
        mock_snapshot = ScreenSnapshot(
            image_bytes=b"dummy",
            base64_jpeg="dummy_b64",
            width=1440,
            height=900,
            original_width=2880,
            original_height=1800,
            scale_factor_x=2.0,
            scale_factor_y=2.0,
            timestamp=123.0,
        )
        mock_capture.return_value = mock_snapshot

        agent = GeminiComputerUse(max_steps=2)
        res = agent.execute_goal("Click the start button")
        assert res.get("success") is True
        assert res.get("steps_executed") >= 1

    @patch("perception.screen_capture.ScreenCapture.capture_screen")
    @patch("automation.action_dispatcher.click_element")
    @patch("automation.action_dispatcher.move_cursor")
    def test_mocked_gemini_vision_action_cycle(self, mock_move, mock_click, mock_capture):
        mock_snapshot = ScreenSnapshot(
            image_bytes=b"dummy",
            base64_jpeg="dummy_b64",
            width=1000,
            height=500,
            original_width=2000,
            original_height=1000,
            scale_factor_x=2.0,
            scale_factor_y=2.0,
            timestamp=123.0,
        )
        mock_capture.return_value = mock_snapshot
        mock_click.return_value = MagicMock(success=True, error=None)

        agent = GeminiComputerUse(max_steps=2)

        # Mock _decide_next_action to return a click action first, then finish
        step_counter = [0]

        def mock_decide(goal, snap, step, hist):
            step_counter[0] += 1
            if step_counter[0] == 1:
                return ComputerAction(
                    action_type="click",
                    x=100,  # on 1000x500 image -> scales to 200 on 2000x1000 desktop
                    y=50,   # scales to 100 on 2000x1000 desktop
                    intent="Click login button",
                    is_completed=False,
                )
            else:
                return ComputerAction(
                    action_type="finish",
                    intent="Task completed",
                    is_completed=True,
                )

        agent._decide_next_action = mock_decide

        action_events = []
        agent.on_action_callback = lambda ev: action_events.append(ev)

        result = agent.execute_goal("Login to application")
        assert result.get("success") is True
        assert len(result.get("trace")) == 2
        # Verify scaled coordinates
        first_step = result["trace"][0]
        assert first_step["x"] == 200
        assert first_step["y"] == 100
        assert len(action_events) == 1
        assert action_events[0]["x"] == 200
        assert action_events[0]["y"] == 100

    @patch("perception.screen_capture.ScreenCapture.capture_screen")
    def test_safety_guard_blocks_hazardous_coordinates(self, mock_capture):
        mock_snapshot = ScreenSnapshot(
            image_bytes=b"dummy",
            base64_jpeg="dummy_b64",
            width=1000,
            height=500,
            original_width=2000,
            original_height=1000,
            scale_factor_x=2.0,
            scale_factor_y=2.0,
            timestamp=123.0,
        )
        mock_capture.return_value = mock_snapshot

        agent = GeminiComputerUse(max_steps=1)
        # Extreme/negative coordinates outside screen
        agent._decide_next_action = lambda g, s, n, h: ComputerAction(
            action_type="click",
            x=-5000,
            y=-5000,
            intent="Hazardous click",
        )

        res = agent.execute_goal("Test safety block")
        assert res.get("success") is False
        assert "Safety guard" in (res["trace"][0]["error"] or "")
