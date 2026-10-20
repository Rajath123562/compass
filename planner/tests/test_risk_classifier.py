"""
Unit tests for Contextual Risk Classifier (Phase 4, Addendum §5, Directive §8, §9).
Validates contextual risk classification and absolute confirmation requirement on HIGH risk.
"""

from planner.models import PlannerActionType, RiskLevel
from planner.risk_classifier import risk_classifier


def test_risk_click_delete_is_high():
    """Directive §8: Click on 'Delete' must be HIGH."""
    res = risk_classifier.classify_risk(
        action=PlannerActionType.CLICK, target_name="Delete"
    )
    assert res.risk_level == RiskLevel.HIGH
    assert res.requires_confirmation is True
    assert res.data_loss_potential is True


def test_risk_click_open_menu_is_low():
    """Directive §8: Click on 'Open menu' may be LOW."""
    res = risk_classifier.classify_risk(
        action=PlannerActionType.CLICK, target_name="Open menu"
    )
    assert res.risk_level == RiskLevel.LOW
    assert res.requires_confirmation is False


def test_risk_click_submit_is_high():
    """Addendum §5: Click on 'Submit' is HIGH due to external side effect."""
    res = risk_classifier.classify_risk(
        action=PlannerActionType.CLICK, target_name="Submit Order"
    )
    assert res.risk_level == RiskLevel.HIGH
    assert res.requires_confirmation is True
    assert res.side_effect_potential is True


def test_risk_alt_f4_combination_is_high():
    """Destructive key combination must be HIGH."""
    res = risk_classifier.classify_risk(
        action=PlannerActionType.KEY_COMBINATION, parameters={"combination": "Alt+F4"}
    )
    assert res.risk_level == RiskLevel.HIGH
    assert res.requires_confirmation is True


def test_risk_observe_and_highlight_are_low():
    res_obs = risk_classifier.classify_risk(action=PlannerActionType.OBSERVE)
    assert res_obs.risk_level == RiskLevel.LOW
    assert res_obs.requires_confirmation is False

    res_hl = risk_classifier.classify_risk(
        action=PlannerActionType.HIGHLIGHT, target_name="Button"
    )
    assert res_hl.risk_level == RiskLevel.LOW
    assert res_hl.requires_confirmation is False
