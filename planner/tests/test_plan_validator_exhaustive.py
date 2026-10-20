"""
COMPASS PlanValidator Exhaustive Tests (COMPASS-AUDIT-017)
Ensures every action type has strict schema validation and risk is not keyword-only.
"""

from __future__ import annotations

import pytest

from planner.models import (
    DecomposedPlan,
    PlannedAction,
    PlannerActionType,
    RiskLevel,
    TaskStep,
)
from planner.plan_validator import PlanValidator


@pytest.fixture
def validator():
    return PlanValidator()


def create_single_step_plan(
    action: PlannedAction,
    goal: str = "Perform action",
    step_goal: str = "Execute action step",
    risk_level: RiskLevel = RiskLevel.LOW,
    repeatability: bool = False,
) -> DecomposedPlan:
    step = TaskStep(
        step_id="step-1",
        goal=step_goal,
        verification_strategy="element_exists",
        risk_level=risk_level,
        repeatability=repeatability,
        candidate_actions=[action],
    )
    return DecomposedPlan(
        task_id="task-123",
        goal=goal,
        steps=[step],
        max_execution_time_s=60.0,
    )


def test_forbidden_param_keys_rejected(validator):
    """Actions with cmd, exec, shell, etc. parameters must be strictly rejected."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="button",
        expected_result="clicked",
        parameters={"cmd": "powershell rm -rf /"},
    )
    plan = create_single_step_plan(action)
    valid, err = validator.validate_plan(plan)
    assert valid is False
    assert "prohibited key" in err.lower()


def test_key_combination_action_validation(validator):
    """KEY_COMBINATION requires valid keys or combination."""
    # Exceeding maximum allowed keys
    bad_action = PlannedAction(
        action_type=PlannerActionType.KEY_COMBINATION,
        target_description="combo",
        expected_result="typed",
        parameters={"keys": ["ctrl", "alt", "shift", "win", "a", "b", "c"]},
    )
    valid, err = validator.validate_plan(create_single_step_plan(bad_action))
    assert valid is False
    assert "maximum 6 keys" in err.lower()

    # Valid combination
    good_action = PlannedAction(
        action_type=PlannerActionType.KEY_COMBINATION,
        target_description="combo",
        expected_result="typed",
        parameters={"keys": ["ctrl", "c"]},
    )
    valid, err = validator.validate_plan(create_single_step_plan(good_action))
    assert valid is True
    assert err is None


def test_click_invalid_button_rejected(validator):
    """CLICK action with invalid button string must be rejected."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="button",
        expected_result="clicked",
        parameters={"button": "fourth_button"},
    )
    valid, err = validator.validate_plan(create_single_step_plan(action))
    assert valid is False
    assert "invalid mouse button" in err.lower()


def test_scroll_extreme_magnitude_rejected(validator):
    """SCROLL with unreasonable delta must be rejected."""
    action = PlannedAction(
        action_type=PlannerActionType.SCROLL,
        target_description="page",
        expected_result="scrolled",
        parameters={"amount": 9999999},
    )
    valid, err = validator.validate_plan(create_single_step_plan(action))
    assert valid is False
    assert "magnitude" in err.lower()


def test_consequential_action_with_benign_goal_flagged(validator):
    """A dangerous action target (e.g. 'delete database') must force HIGH/CONSEQUENTIAL risk even if goal sounds benign."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Click 'Delete All Records' Button",
        expected_result="Records purged",
        parameters={"button": "left"},
    )
    # Goal sounds benign: "Organize project files"
    plan = create_single_step_plan(
        action,
        goal="Organize project files",
        step_goal="Clean up project folders",
        risk_level=RiskLevel.LOW,  # Incorrectly classified as LOW
    )
    valid, err = validator.validate_plan(plan)
    assert valid is False
    assert "must be high or consequential" in err.lower()
