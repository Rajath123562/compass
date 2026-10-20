"""
Unit tests for VerificationEngine and Post-Action State Transitions.
"""

from planner.models import (
    PlannedAction,
    PlannerActionType,
    VerificationCondition,
    VerificationStatus,
)
from planner.verification_engine import VerificationEngine


class TestVerificationEngine:
    def setup_method(self):
        self.verifier = VerificationEngine(default_poll_interval_s=0.05)

    def test_wait_verification(self):
        action = PlannedAction(
            action_type=PlannerActionType.WAIT,
            target_description="Pause",
            expected_result="Paused",
            parameters={"duration_ms": 100},
        )
        res = self.verifier.verify_action(action, post_snapshot={})
        assert res.status == VerificationStatus.VERIFIED

    def test_text_verification_success(self):
        action = PlannedAction(
            action_type=PlannerActionType.TYPE,
            target_description="Text input",
            expected_result="Text entered",
            parameters={"text": "hello"},
            verification_condition=VerificationCondition(
                condition_type="text_equals", expected_value="hello", timeout_ms=300
            ),
        )
        snapshot = {
            "elements": [
                {"name": "hello world", "automation_id": "txt1", "control_type": "Edit"}
            ]
        }
        res = self.verifier.verify_action(
            action, post_snapshot=snapshot, resolved_element={"automation_id": "txt1"}
        )
        assert res.status == VerificationStatus.VERIFIED
        assert "hello" in res.details

    def test_text_verification_failure(self):
        action = PlannedAction(
            action_type=PlannerActionType.TYPE,
            target_description="Text input",
            expected_result="Text entered",
            parameters={"text": "expected_word"},
            verification_condition=VerificationCondition(
                condition_type="text_equals",
                expected_value="expected_word",
                timeout_ms=200,
            ),
        )
        snapshot = {
            "elements": [
                {
                    "name": "totally_different_text",
                    "automation_id": "txt1",
                    "control_type": "Edit",
                }
            ]
        }
        res = self.verifier.verify_action(
            action, post_snapshot=snapshot, resolved_element={"automation_id": "txt1"}
        )
        assert res.status == VerificationStatus.FAILED

    def test_launch_app_infer_verification(self):
        action = PlannedAction(
            action_type=PlannerActionType.LAUNCH_APP,
            target_description="Notepad Window",
            expected_result="Notepad launched",
            parameters={"app": "notepad.exe", "path": "notepad.exe"},
        )
        snapshot = {
            "window": {"title": "Untitled - Notepad", "hwnd": 12345},
            "elements": [],
        }
        res = self.verifier.verify_action(action, post_snapshot=snapshot)
        assert res.status == VerificationStatus.VERIFIED
        assert "Notepad" in res.details

    def test_launch_app_with_window_title_condition(self):
        action = PlannedAction(
            action_type=PlannerActionType.LAUNCH_APP,
            target_description="Notepad Window",
            expected_result="Notepad launched",
            parameters={"app": "notepad.exe"},
            verification_condition=VerificationCondition(
                condition_type="window_title_contains",
                expected_value="Notepad",
                timeout_ms=300,
            ),
        )
        snapshot = {
            "window": {"title": "Untitled - Notepad", "hwnd": 12345},
            "elements": [],
        }
        res = self.verifier.verify_action(action, post_snapshot=snapshot)
        assert res.status == VerificationStatus.VERIFIED

    def test_open_url_verification(self):
        action = PlannedAction(
            action_type=PlannerActionType.OPEN_URL,
            target_description="ChatGPT",
            expected_result="ChatGPT opened",
            parameters={"url": "https://chatgpt.com/"},
        )
        res = self.verifier.verify_action(action, post_snapshot={})
        assert res.status == VerificationStatus.VERIFIED
        assert "chatgpt.com" in res.details

