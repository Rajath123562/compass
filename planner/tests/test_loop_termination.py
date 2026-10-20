"""
Unit tests for LoopDetector (Phase 6, Capability O, §17, §19).
Verifies action failure loop detection, state oscillation cycles, and replan limits.
"""

from planner.loop_detector import LoopDetector


def test_repeated_action_failure_loop_detected():
    """Detects repeated consecutive action failures on the same target."""
    ld = LoopDetector(max_repeated_actions=3)

    is_loop, _ = ld.record_action_attempt("click", "btn_submit", False, "FAILED")
    assert is_loop is False

    is_loop, _ = ld.record_action_attempt("click", "btn_submit", False, "FAILED")
    assert is_loop is False

    # Third failure exceeds threshold
    is_loop, reason = ld.record_action_attempt("click", "btn_submit", False, "FAILED")
    assert is_loop is True
    assert "failed 3 consecutive times" in reason


def test_action_success_resets_failure_streak():
    """Successful action breaks the consecutive failure counter."""
    ld = LoopDetector(max_repeated_actions=3)
    ld.record_action_attempt("click", "btn_submit", False, "FAILED")
    ld.record_action_attempt("click", "btn_submit", False, "FAILED")
    # Intervening success
    ld.record_action_attempt("click", "btn_submit", True, "VERIFIED")

    is_loop, _ = ld.record_action_attempt("click", "btn_submit", False, "FAILED")
    assert is_loop is False


def test_state_oscillation_cycle_detected():
    """Detects A -> B -> A -> B state oscillation cycles."""
    ld = LoopDetector()

    ld.record_ui_state("state_A")
    ld.record_ui_state("state_B")
    ld.record_ui_state("state_A")
    is_loop, reason = ld.record_ui_state("state_B")

    assert is_loop is True
    assert "State oscillation cycle detected" in reason


def test_replan_limit_enforced():
    """Enforces maximum allowable replan count to prevent infinite replanning."""
    ld = LoopDetector(max_replans=2)

    is_loop, _ = ld.record_replan("hash_1")
    assert is_loop is False

    is_loop, _ = ld.record_replan("hash_2")
    assert is_loop is False

    # Third replan exceeds max_replans=2
    is_loop, reason = ld.record_replan("hash_3")
    assert is_loop is True
    assert "Maximum replan limit" in reason


def test_cyclic_replan_detected():
    """Detects regeneration of an identical plan hash."""
    ld = LoopDetector(max_replans=5)

    ld.record_replan("plan_hash_alpha")
    ld.record_replan("plan_hash_beta")
    is_loop, reason = ld.record_replan("plan_hash_alpha")

    assert is_loop is True
    assert "Cyclic replan detected" in reason
