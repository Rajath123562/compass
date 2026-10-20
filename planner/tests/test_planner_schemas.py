"""
Unit tests for Planner Pydantic Schemas, Action Allowlist, and Bounds Validation.
"""

import pytest
from pydantic import ValidationError

from planner.models import (
    ConfidenceLevel,
    PlannedAction,
    PlannerActionType,
    TargetReference,
    TaskPlan,
)


class TestPlannerSchemas:
    def test_valid_task_plan_creation(self):
        plan = TaskPlan(
            task_id="task_100",
            goal="Open text editor and type test",
            reasoning_summary="Focus editor and enter text",
            steps=[
                PlannedAction(
                    action_type=PlannerActionType.FOCUS,
                    target_reference=TargetReference(
                        name="Editor", control_type="Edit"
                    ),
                    target_description="Notepad text area",
                    expected_result="Editor focused",
                    confidence=ConfidenceLevel.HIGH,
                ),
                PlannedAction(
                    action_type=PlannerActionType.TYPE,
                    target_reference=TargetReference(
                        name="Editor", control_type="Edit"
                    ),
                    target_description="Notepad text area",
                    parameters={"text": "Hello COMPASS"},
                    expected_result="Text typed",
                    confidence=ConfidenceLevel.HIGH,
                ),
            ],
        )
        assert plan.task_id == "task_100"
        assert len(plan.steps) == 2
        assert plan.steps[0].action_type == PlannerActionType.FOCUS
        assert plan.steps[1].parameters["text"] == "Hello COMPASS"

    def test_unsupported_action_type_rejected(self):
        with pytest.raises(ValidationError):
            PlannedAction(
                action_type="shell_exec",  # Invalid action type
                target_description="Run bash",
                expected_result="Command executed",
            )

    def test_type_action_missing_text_rejected(self):
        with pytest.raises(ValueError, match="requires 'text' parameter"):
            PlannedAction(
                action_type=PlannerActionType.TYPE,
                target_description="Editor",
                expected_result="Typed",
                parameters={},  # Missing text
            )

    def test_type_action_oversized_text_rejected(self):
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            PlannedAction(
                action_type=PlannerActionType.TYPE,
                target_description="Editor",
                expected_result="Typed",
                parameters={"text": "A" * 15000},
            )

    def test_key_action_invalid_key_rejected(self):
        with pytest.raises(ValueError, match="not an allowlisted virtual key code"):
            PlannedAction(
                action_type=PlannerActionType.KEY,
                target_description="Key",
                expected_result="Sent",
                parameters={"key": "NonExistentKey123"},
            )

    def test_wait_duration_bounds(self):
        with pytest.raises(ValueError, match="Wait duration must be between"):
            PlannedAction(
                action_type=PlannerActionType.WAIT,
                target_description="Wait",
                expected_result="Wait",
                parameters={"duration_ms": 20000},  # Over 10000 limit
            )
