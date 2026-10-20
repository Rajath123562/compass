"""
Unit tests for Phase 5 3-Stage Adaptive Recovery Protocol
(P5-REQ-005, P5-REQ-006, P5-REQ-007, P5-REQ-008)
"""

from planner.models import FailureState, PlannedAction, PlannerActionType
from planner.recovery_engine import RecoveryStage, recovery_engine


def test_stage_1_reperception_detects_drift():
    """Stage 1: Detects coordinate drift and re-aligns target bounds."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Save Button",
        expected_result="File saved",
    )
    old_target = {
        "name": "Save Button",
        "automation_id": "btn_save",
        "bounds": {"left": 100, "top": 100, "right": 200, "bottom": 150},
    }
    # Target moved 30px right and 10px down
    new_target = {
        "name": "Save Button",
        "automation_id": "btn_save",
        "bounds": {"left": 130, "top": 110, "right": 230, "bottom": 160},
    }
    snapshot = {"elements": [new_target]}

    res = recovery_engine.stage_1_reobserve(action, old_target, snapshot)
    assert res.stage == RecoveryStage.STAGE_1_REPERCEIVE
    assert res.success is True
    assert res.strategy == "COORDINATE_REALIGN"
    assert res.target_element["bounds"]["left"] == 130
    assert "dx=30px, dy=10px" in res.reason


def test_stage_1_missing_target_fails():
    """Stage 1: Fails gracefully when target cannot be found in re-observed UI."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Cancel Button",
        expected_result="Dialog closed",
    )
    old_target = {"name": "Cancel Button", "automation_id": "btn_cancel"}
    snapshot = {"elements": [{"name": "OK Button", "automation_id": "btn_ok"}]}

    res = recovery_engine.stage_1_reobserve(action, old_target, snapshot)
    assert res.success is False
    assert res.strategy == "TARGET_MISSING"


def test_stage_2_blocks_non_repeatable_action():
    """Stage 2: Non-repeatable consequential action must NEVER be automatically retried."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Delete Account Permanently",
        expected_result="Account deleted",
        safety_class="consequential",
    )
    target = {"name": "Delete Account", "is_enabled": True}

    res = recovery_engine.stage_2_targeted_retry(
        action=action,
        target_element=target,
        attempt_count=0,
        max_retries=2,
        is_repeatable=False,
    )
    assert res.success is False
    assert res.strategy == "HALT_NON_REPEATABLE"
    assert res.is_terminal is True
    assert "strictly prohibited" in res.reason


def test_stage_2_retry_budget_exhaustion():
    """Stage 2: Rejects retry once attempt count reaches max_retries."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Refresh Page",
        expected_result="Page refreshed",
    )
    target = {"name": "Refresh", "is_enabled": True}

    res = recovery_engine.stage_2_targeted_retry(
        action=action,
        target_element=target,
        attempt_count=2,
        max_retries=2,
        is_repeatable=True,
    )
    assert res.success is False
    assert res.strategy == "RETRIES_EXHAUSTED"


def test_stage_2_disabled_target_rejection():
    """Stage 2: Rejects retry if live target element is disabled."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Next",
        expected_result="Next page loaded",
    )
    target = {"name": "Next", "is_enabled": False}

    res = recovery_engine.stage_2_targeted_retry(
        action=action,
        target_element=target,
        attempt_count=0,
        max_retries=2,
        is_repeatable=True,
    )
    assert res.success is False
    assert res.strategy == "TARGET_DISABLED"


def test_stage_2_authorized_retry():
    """Stage 2: Authorizes retry for valid, enabled repeatable action within budget."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Expand Tree View",
        expected_result="Tree expanded",
    )
    target = {"name": "Expand Tree View", "is_enabled": True}

    res = recovery_engine.stage_2_targeted_retry(
        action=action,
        target_element=target,
        attempt_count=0,
        max_retries=2,
        is_repeatable=True,
    )
    assert res.success is True
    assert res.strategy == "RETRY_ACTION"
    assert "attempt 1/2" in res.reason


def test_stage_3_semantic_invoke_pattern():
    """Stage 3: Dispatches semantic InvokePattern if click verification failed."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Menu Item",
        expected_result="Menu item invoked",
    )
    target = {
        "name": "Menu Item",
        "available_patterns": ["InvokePattern", "SelectionItemPattern"],
    }

    res = recovery_engine.stage_3_alternate_strategy(action, target)
    assert res.success is True
    assert res.strategy == "SEMANTIC_INVOKE"


def test_stage_3_semantic_toggle_pattern():
    """Stage 3: Dispatches semantic TogglePattern if toggle button click failed."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="Enable Notifications",
        expected_result="Notifications enabled",
    )
    target = {"name": "Enable Notifications", "available_patterns": ["TogglePattern"]}

    res = recovery_engine.stage_3_alternate_strategy(action, target)
    assert res.success is True
    assert res.strategy == "SEMANTIC_TOGGLE"


def test_stage_3_keyboard_shortcut_fallback():
    """Stage 3: Substitutes Enter key shortcut for failed Submit/OK click."""
    action = PlannedAction(
        action_type=PlannerActionType.CLICK,
        target_description="OK",
        expected_result="Dialog submitted",
    )
    target = {"name": "OK", "available_patterns": []}

    res = recovery_engine.stage_3_alternate_strategy(action, target)
    assert res.success is True
    assert res.strategy == "KEYBOARD_SHORTCUT"
    assert res.action_to_dispatch.action_type == PlannerActionType.KEY
    assert res.action_to_dispatch.parameters["key"] == "enter"


def test_stage_3_fallback_triggers_replan():
    """Stage 3: Triggers full replan when no semantic or shortcut alternative exists."""
    action = PlannedAction(
        action_type=PlannerActionType.SCROLL,
        target_description="Custom Canvas",
        expected_result="Canvas scrolled",
    )
    target = {"name": "Custom Canvas", "available_patterns": []}

    res = recovery_engine.stage_3_alternate_strategy(action, target)
    assert res.success is False
    assert res.strategy == "TRIGGER_REPLAN"


def test_extended_failure_classifications_diagnosis():
    """Verifies that all Phase 5 extended failure classifications are properly diagnosed."""
    cases = [
        ("APPLICATION_CRASHED", "HALT", FailureState.APPLICATION_CLOSED),
        ("PROCESS_TERMINATED", "HALT", FailureState.APPLICATION_CLOSED),
        ("WINDOW_UNRESPONSIVE", "HALT", FailureState.APPLICATION_CLOSED),
        ("TARGET_DISABLED", "ASK_USER", FailureState.BLOCKED),
        ("ACTION_UNVERIFIED", "REOBSERVE_AND_REPLAN", FailureState.VERIFICATION_FAILED),
        ("RESOURCE_EXHAUSTED", "HALT", FailureState.BLOCKED),
        ("HUMAN_TAKEOVER", "REOBSERVE_AND_REPLAN", FailureState.USER_CANCELLED),
    ]

    for cause, expected_strat, expected_state in cases:
        diag = recovery_engine.diagnose_failure(
            cause=cause,
            task_id="task_p5_diag",
            original_goal="Diagnose extended failure states",
            total_steps=3,
            failed_step_index=1,
            verified_step_indices=[0],
            details=f"Testing {cause}",
        )
        assert diag.recommended_strategy == expected_strat, (
            f"Strategy mismatch for {cause}"
        )
        assert diag.resulting_failure_state == expected_state, (
            f"State mismatch for {cause}"
        )
        assert diag.preserve_completed_steps is True
