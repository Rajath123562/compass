"""
Unit tests for Goal Understanding Engine (Phase 4).
Validates intent extraction, application parsing, ambiguity detection, and risk baseline.
"""

from planner.goal_understanding import goal_understanding_engine
from planner.models import RiskLevel


def test_goal_understanding_notepad_typing():
    res = goal_understanding_engine.understand_goal(
        "Open Notepad and type 'Hello World'"
    )
    assert res.target_application == "Notepad"
    assert res.target_application_executable == "notepad.exe"
    assert res.is_ambiguous is False
    assert res.safety_level == RiskLevel.LOW
    assert "text_input" in res.required_capabilities
    assert "Expected text entered" in res.desired_final_state


def test_goal_understanding_calculator():
    res = goal_understanding_engine.understand_goal(
        "Click 5 on Calculator and press plus"
    )
    assert res.target_application == "Calculator"
    assert res.is_ambiguous is False
    assert res.safety_level == RiskLevel.LOW
    assert "click" in res.required_capabilities


def test_goal_understanding_high_risk_deletion():
    res = goal_understanding_engine.understand_goal(
        "Delete all temporary files in folder"
    )
    assert res.safety_level == RiskLevel.HIGH
    assert res.is_ambiguous is False


def test_goal_understanding_ambiguous_short_goal():
    res = goal_understanding_engine.understand_goal("fix")
    assert res.is_ambiguous is True
    assert res.clarification_question is not None


def test_goal_understanding_ambiguous_vague_phrase():
    res = goal_understanding_engine.understand_goal("do it")
    assert res.is_ambiguous is True
    assert res.clarification_question is not None
