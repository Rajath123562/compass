"""
COMPASS Phase 5: False-Success Detection Suite (P5-REQ-013)
Tests that COMPASS strictly detects cases where the underlying OS or automation API
reports technical success, but the intended UI state transition failed to occur.
A technical API success must NEVER automatically equate to task success.
"""

from planner.models import PlannedAction, PlannerActionType, VerificationStatus
from planner.verification_engine import verification_engine


def test_click_api_success_but_dialog_did_not_open():
    """API reports click success, but expected modal window or element did not open."""
    action = PlannedAction(  # noqa: F841
        step_number=1,
        action_type=PlannerActionType.CLICK,
        target_description="Settings Button",
        expected_result="Settings Modal Dialog",
    )
    pre_snapshot = {
        "window": {"hwnd": 100, "title": "Main App"},
        "elements": [{"name": "Settings Button", "control_type": "Button"}],
    }
    # Post-action snapshot has same elements; modal did NOT appear
    post_snapshot = {
        "window": {"hwnd": 100, "title": "Main App"},
        "elements": [{"name": "Settings Button", "control_type": "Button"}],
    }

    res = verification_engine.verify_click_transition(
        target_element={"name": "Settings Button"},
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        expected_outcome="Settings Modal Dialog",
    )
    assert res.status == VerificationStatus.UNVERIFIED
    assert (
        "no observable UI state change detected" in res.details.lower()
        or "unverified" in res.status.value.lower()
    )


def test_typing_api_success_but_text_missing_from_control():
    """SendInput reported success, but expected text is missing from target control."""
    action = PlannedAction(
        step_number=1,
        action_type=PlannerActionType.TYPE,
        target_description="Search Box",
        expected_result="Search text entered",
        parameters={"text": "COMPASS Secure Query"},
    )
    target_element = {
        "name": "Search Box",
        "control_type": "Edit",
        "text": "",  # Text failed to type!
        "hwnd": 100,
    }
    post_snapshot = {
        "window": {"hwnd": 100, "title": "Main App"},
        "elements": [target_element],
    }

    res = verification_engine.verify_action(
        action=action, post_snapshot=post_snapshot, resolved_element=target_element
    )
    assert res.status == VerificationStatus.FAILED
    assert (
        "typing verification failed" in res.details.lower()
        or "not found" in res.details.lower()
    )


def test_app_launch_reported_but_window_never_appeared():
    """Process spawn returned success, but window did not appear or wrong window active."""
    post_snapshot = {
        "window": {"hwnd": 100, "title": "Desktop Explorer"},
        "elements": [],
    }
    res = verification_engine.verify_app_launch("Notepad", post_snapshot)
    assert res.status == VerificationStatus.FAILED
    assert "launch verification failed" in res.details.lower()


def test_toggle_click_but_state_remains_unchanged():
    """Toggle button clicked, but ToggleState did not change."""
    action = PlannedAction(
        step_number=1,
        action_type=PlannerActionType.CLICK,
        target_description="Dark Mode Toggle",
        expected_result="Dark Mode Enabled",
        parameters={"expected_toggle": "ON"},
    )
    target_element = {
        "name": "Dark Mode Toggle",
        "control_type": "Button",
        "toggle_state": "OFF",  # State remained OFF!
        "hwnd": 100,
    }
    post_snapshot = {
        "window": {"hwnd": 100, "title": "Preferences"},
        "elements": [target_element],
    }

    res = verification_engine.verify_action(
        action=action, post_snapshot=post_snapshot, resolved_element=target_element
    )
    assert res.status == VerificationStatus.FAILED
    assert "toggle verification failed" in res.details.lower()


def test_stale_ui_cache_reports_success_when_live_ui_changed():
    """Action executed, but element became invalid or closed immediately after."""
    action = PlannedAction(
        step_number=1,
        action_type=PlannerActionType.FOCUS,
        target_description="Temporary Popup Item",
        expected_result="Item focused",
    )
    # HWND is 999999 (non-existent dead window)
    dead_element = {
        "name": "Temporary Popup Item",
        "hwnd": 999999,
        "runtime_id": "999999:item",
    }
    post_snapshot = {"window": {"hwnd": 999999}, "elements": []}

    res = verification_engine.verify_action(
        action=action, post_snapshot=post_snapshot, resolved_element=dead_element
    )
    assert res.status in [VerificationStatus.UNCERTAIN, VerificationStatus.FAILED]


def test_action_success_with_unobservable_outcome_returns_unverified():
    """Action executes with no observable state change; must return UNVERIFIED."""
    action = PlannedAction(
        step_number=1,
        action_type=PlannerActionType.MOVE,
        target_description="Passive Icon",
        expected_result="Hover over icon",
    )
    res = verification_engine.verify_unobservable_action(
        action,
        reason="Hover over passive element produces no structural UIA tree change",
    )
    assert res.status == VerificationStatus.UNVERIFIED
    assert "unverified" in res.details.lower()
