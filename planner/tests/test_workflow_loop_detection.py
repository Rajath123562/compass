"""
Tests for Phase 8 Loop and Oscillation Detection (Gate 28).
"""

from planner.loop_detector import LoopDetector


def test_repeated_action_failure_detection():
    detector = LoopDetector(max_repeated_actions=3)

    # 1st attempt: no loop
    detected, _ = detector.record_action_attempt("click", "target_btn", False, "FAILED")
    assert not detected

    # 2nd attempt: no loop
    detected, _ = detector.record_action_attempt("click", "target_btn", False, "FAILED")
    assert not detected

    # 3rd attempt: loop detected!
    detected, reason = detector.record_action_attempt(
        "click", "target_btn", False, "FAILED"
    )
    assert detected
    assert "Loop detected" in reason


def test_state_oscillation_detection():
    detector = LoopDetector(max_state_oscillations=2)

    # State A -> B -> A -> B
    state_A = "window:Notepad|text:hello"
    state_B = "window:Notepad|text:world"

    assert not detector.record_ui_state(state_A)[0]
    assert not detector.record_ui_state(state_B)[0]
    assert not detector.record_ui_state(state_A)[0]
    # Fourth snapshot completes second cycle
    detected, reason = detector.record_ui_state(state_B)
    assert detected
    assert "oscillation" in reason.lower()
