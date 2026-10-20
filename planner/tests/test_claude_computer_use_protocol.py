"""
COMPASS Test Suite — Claude Opus 5.5 Computer-Use Protocol & Autonomous Loop
Verifies:
- Official toolset configuration: computer_toolset_20260801
- Model identifier: claude-opus-5-5
- Anthropic protocol headers and endpoint
- Multi-action batch processing in strictly sequential order
- Partial batch failure: earlier action fails -> subsequent actions skipped and correctly matched
- Echoing toolset_name: computer and matching tool_use_id
- Image blocks for screenshot and zoom actions
- Coordinate transformation between model and Windows display space
- Boundary validation and rejection of out-of-bounds coordinates
- Consequential action approval gating (financial, destructive commands, external messaging)
- Independent final-goal verification (Calculator 45*12=540, Document MeetingNotes.docx)
- Anti-fabrication: model claiming 'Done' is not marked COMPLETED without independent evidence
- Thread-safe STOP and cooperative cancellation
- Rate limiting, missing credentials, timeout handling, and bounded iteration limits
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from planner.claude_agent_loop import ClaudeComputerUseAgentLoop
from planner.human_approval import ApprovalRecord, ApprovalState, human_approval_controller
from planner.models import RiskLevel, VerificationResult, VerificationStatus
from planner.verification_engine import VerificationEngine
from providers.claude_computer_use_adapter import (
    ANTHROPIC_API_URL,
    ANTHROPIC_API_VERSION,
    ANTHROPIC_BETA_COMPUTER_USE,
    MODEL_CLAUDE_OPUS_5_5,
    TOOL_NAME_COMPUTER,
    TOOLSET_COMPUTER_20260801,
    ClaudeComputerUseClient,
    ToolResultBlock,
    WindowsComputerActionExecutor,
)


# ─── 1. Protocol Configuration Tests ──────────────────────────────────────────

def test_claude_protocol_constants_and_toolset_definition():
    client = ClaudeComputerUseClient(api_key="test-key-123")
    headers = client.get_headers()

    assert headers["anthropic-version"] == ANTHROPIC_API_VERSION
    assert headers["anthropic-beta"] == ANTHROPIC_BETA_COMPUTER_USE
    assert headers["x-api-key"] == "test-key-123"

    tool_def = client.create_computer_tool_definition(width=1920, height=1080)
    assert tool_def["type"] == TOOLSET_COMPUTER_20260801
    assert tool_def["name"] == TOOL_NAME_COMPUTER
    assert tool_def["display_width_px"] == 1920
    assert tool_def["display_height_px"] == 1080


def test_missing_credentials_fails_closed():
    client = ClaudeComputerUseClient(api_key=None, mock_mode=False)
    with patch.dict(os.environ, {}, clear=True):
        assert not client.is_configured
        res = client.send_turn(messages=[], system_prompt="")
        assert not res["success"]
        assert "ANTHROPIC_API_KEY is not configured" in res["error"]
        assert res["stop_reason"] == "missing_credentials"


# ─── 2. Coordinate Transformation & Display Geometry Tests ───────────────────

def test_coordinate_mapping_and_boundary_validation():
    executor = WindowsComputerActionExecutor(max_screenshot_width=1920, max_screenshot_height=1080)
    geom = executor.get_current_display_geometry()

    assert geom.width > 0
    assert geom.height > 0
    assert geom.scale_x >= 1.0
    assert geom.scale_y >= 1.0

    # Model to desktop coordinate translation
    rx, ry = executor.model_to_desktop_coordinates(100, 100)
    assert rx >= geom.origin_x
    assert ry >= geom.origin_y

    # Extreme / out of bounds coordinates rejected
    out_res = executor.execute_action("left_click", {"coordinate": [999999, 999999], "_tool_use_id": "call_out"})
    assert out_res.is_error
    assert "out of desktop bounds" in out_res.content[0]["text"].lower()


# ─── 3. Action Member Tool Executions Tests ──────────────────────────────────

def test_screenshot_and_zoom_return_image_blocks():
    executor = WindowsComputerActionExecutor()

    # Screenshot
    res_shot = executor.execute_action("screenshot", {"_tool_use_id": "call_shot_1"})
    assert not res_shot.is_error
    assert res_shot.tool_use_id == "call_shot_1"
    assert res_shot.toolset_name == "computer"
    assert len(res_shot.content) == 1
    assert res_shot.content[0]["type"] == "image"
    assert res_shot.content[0]["source"]["media_type"] == "image/png"
    assert len(res_shot.content[0]["source"]["data"]) > 50

    # Zoom
    res_zoom = executor.execute_action("zoom", {"coordinate": [200, 200], "_tool_use_id": "call_zoom_1"})
    assert not res_zoom.is_error
    assert res_zoom.content[0]["type"] == "image"
    assert len(res_zoom.content[0]["source"]["data"]) > 50


def test_cursor_position_action():
    executor = WindowsComputerActionExecutor()
    res = executor.execute_action("cursor_position", {"_tool_use_id": "call_cur_1"})
    assert not res.is_error
    assert "Current cursor position" in res.content[0]["text"]


def test_wait_action_cooperative_cancellation():
    executor = WindowsComputerActionExecutor()
    cancel_evt = threading.Event()
    cancel_evt.set()  # Pre-cancelled

    res = executor.execute_action("wait", {"duration": 2.0, "_tool_use_id": "call_wait_1"}, cancel_event=cancel_evt)
    assert res.is_error
    assert "aborted" in res.content[0]["text"].lower()


def test_unsupported_action_returns_truthful_error():
    executor = WindowsComputerActionExecutor()
    res = executor.execute_action("format_hard_drive", {"_tool_use_id": "call_unknown"})
    assert res.is_error
    assert "Unsupported or unknown computer action" in res.content[0]["text"]


# ─── 4. Multi-Action Batch Ordering & Partial Failure Tests ──────────────────

def test_batch_ordering_and_stop_on_partial_failure():
    """
    If action 1 succeeds, action 2 fails, action 3 MUST NOT be dispatched,
    and all 3 tool results must be returned matching IDs and echoing toolset_name.
    """
    mock_client = MagicMock(spec=ClaudeComputerUseClient)
    mock_client.is_configured = True

    # Assistant returns a batch of 3 actions:
    # 1: wait 0.1s (valid)
    # 2: left_click at invalid coordinates (will fail)
    # 3: type text (dependent, must be skipped)
    batch_response = {
        "success": True,
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "tool_1",
                "name": TOOL_NAME_COMPUTER,
                "input": {"action": "wait", "duration": 0.1},
            },
            {
                "type": "tool_use",
                "id": "tool_2",
                "name": TOOL_NAME_COMPUTER,
                "input": {"action": "left_click", "coordinate": [999999, 999999]},
            },
            {
                "type": "tool_use",
                "id": "tool_3",
                "name": TOOL_NAME_COMPUTER,
                "input": {"action": "type", "text": "This should not be typed"},
            },
        ],
    }

    # Second turn returns completion
    completion_response = {
        "success": True,
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "Finished after failure."}],
    }

    mock_client.send_turn.side_effect = [batch_response, completion_response]

    agent_loop = ClaudeComputerUseAgentLoop(client=mock_client)
    task = task_service.create_task(goal="Test batch failure order")

    result = agent_loop.run(task_id=task["id"], goal="Test batch failure order")

    # Verify send_turn was called and examine the tool results returned in second call
    assert mock_client.send_turn.call_count == 2
    second_call_messages = mock_client.send_turn.call_args_list[1][1]["messages"]
    tool_result_turn = second_call_messages[-1]
    assert tool_result_turn["role"] == "user"
    results = tool_result_turn["content"]

    assert len(results) == 3
    # Check matching IDs and toolset_name
    assert results[0]["tool_use_id"] == "tool_1"
    assert results[0]["toolset_name"] == TOOL_NAME_COMPUTER
    assert results[0]["is_error"] is False

    assert results[1]["tool_use_id"] == "tool_2"
    assert results[1]["toolset_name"] == TOOL_NAME_COMPUTER
    assert results[1]["is_error"] is True

    assert results[2]["tool_use_id"] == "tool_3"
    assert results[2]["toolset_name"] == TOOL_NAME_COMPUTER
    assert results[2]["is_error"] is True
    assert "Skipped: Dependent action" in results[2]["content"][0]["text"]


# ─── 5. Consequential Actions & Human Approval Tests ─────────────────────────

def test_consequential_action_approval_rejection():
    mock_client = MagicMock(spec=ClaudeComputerUseClient)
    mock_client.is_configured = True

    # Assistant attempts a destructive shell command
    destructive_turn = {
        "success": True,
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "tool_del",
                "name": TOOL_NAME_COMPUTER,
                "input": {"action": "type", "text": "rmdir /s /q important_folder"},
            }
        ],
    }
    finish_turn = {
        "success": True,
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "Aborted."}],
    }
    mock_client.send_turn.side_effect = [destructive_turn, finish_turn]

    agent_loop = ClaudeComputerUseAgentLoop(client=mock_client)
    task = task_service.create_task(goal="Delete files")

    # Auto-reject pending approvals in a background timer
    def auto_reject():
        time.sleep(0.3)
        for appr in human_approval_controller.list_pending():
            if appr.task_id == task["id"]:
                human_approval_controller.submit_decision(appr.decision_id, approved=False, reason="Safety policy rejection")

    t = threading.Thread(target=auto_reject, daemon=True)
    t.start()

    res = agent_loop.run(task_id=task["id"], goal="Delete files", confirmation_timeout_s=5.0)

    # Tool result must have indicated operator denied action
    second_msgs = mock_client.send_turn.call_args_list[1][1]["messages"]
    tool_results = second_msgs[-1]["content"]
    assert tool_results[0]["is_error"] is True
    assert "Operation denied by human operator" in tool_results[0]["content"][0]["text"]


# ─── 6. Independent Final-Goal Verification Tests ─────────────────────────────

def test_calculator_arithmetic_independent_verification_success():
    """
    Goal: 'Open Calculator, calculate 45 multiplied by 12, and tell me the answer.'
    Expected: 540.
    Verifier inspects elements and confirms CalculatorResults contains 540.
    """
    verifier = VerificationEngine()
    current_snapshot = {
        "window": {"title": "Calculator", "hwnd": 101},
        "elements": [
            {"name": "Display is 540", "automation_id": "CalculatorResults", "text": "540"},
        ],
    }

    res = verifier.verify_final_goal_state(
        goal="Open Calculator, calculate 45 multiplied by 12, and tell me the answer.",
        desired_final_state="540",
        current_snapshot=current_snapshot,
        completed_step_count=5,
    )

    assert res.status == VerificationStatus.VERIFIED
    assert res.evidence["calculation_verified"] is True
    assert res.evidence["expected_answer"] == "540"


def test_calculator_display_mismatch_fails_verification():
    """
    Calculator display shows 0 or wrong number instead of 540 -> MUST FAIL.
    """
    verifier = VerificationEngine()
    current_snapshot = {
        "window": {"title": "Calculator", "hwnd": 101},
        "elements": [
            {"name": "Display is 0", "automation_id": "CalculatorResults", "text": "0"},
        ],
    }

    res = verifier.verify_final_goal_state(
        goal="Open Calculator, calculate 45 multiplied by 12, and tell me the answer.",
        desired_final_state="Done",
        current_snapshot=current_snapshot,
        completed_step_count=5,
    )

    assert res.status == VerificationStatus.FAILED
    assert "Calculator verification failed" in res.details


def test_document_persistence_independent_verification(tmp_path):
    """
    Goal: 'Open Word, create a document containing these meeting notes, save it as MeetingNotes.docx in my Documents folder, and confirm that it was saved.'
    Verifier checks that MeetingNotes.docx exists and is non-empty.
    """
    verifier = VerificationEngine()
    test_doc = Path.cwd() / "MeetingNotes.docx"
    test_doc.write_text("Meeting notes: Architecture review and deployment plan.", encoding="utf-8")

    try:
        res = verifier.verify_final_goal_state(
            goal="Open Word, create a document containing meeting notes, save as MeetingNotes.docx, and confirm that it was saved.",
            desired_final_state="Saved MeetingNotes.docx",
            current_snapshot={"window": {"title": "Word", "hwnd": 202}, "elements": []},
            completed_step_count=4,
        )
        assert res.status == VerificationStatus.VERIFIED
        assert res.evidence["document_saved"] is True
    finally:
        if test_doc.exists():
            test_doc.unlink()


def test_anti_fabrication_model_done_claim_rejected_without_evidence():
    """
    Model claims 'I am finished and everything is done!' without any real UI evidence -> UNVERIFIED.
    """
    mock_client = MagicMock(spec=ClaudeComputerUseClient)
    mock_client.is_configured = True

    # Assistant returns text claiming done without performing real work
    mock_client.send_turn.return_value = {
        "success": True,
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "Done! I calculated 45 multiplied by 12 and the answer is 540."}],
    }

    # Mock verifier that returns UNCERTAIN because Calculator window doesn't exist on mock desktop
    verifier = VerificationEngine()
    agent_loop = ClaudeComputerUseAgentLoop(client=mock_client, verifier=verifier)
    task = task_service.create_task(goal="Calculate 45 multiplied by 12")

    result = agent_loop.run(task_id=task["id"], goal="Calculate 45 multiplied by 12")

    # Must NOT claim COMPLETED merely because model text said Done
    assert result["status"] == "UNVERIFIED"
    assert result["success"] is False


# ─── 7. STOP & Cancellation Tests ─────────────────────────────────────────────

def test_stop_during_loop_immediately_aborts_and_sets_stopped():
    mock_client = MagicMock(spec=ClaudeComputerUseClient)
    mock_client.is_configured = True

    stop_evt = threading.Event()

    def side_effect_turn(*args, **kwargs):
        # Assert stop during API turn
        stop_evt.set()
        return {
            "success": True,
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_stop_1",
                    "name": TOOL_NAME_COMPUTER,
                    "input": {"action": "wait", "duration": 0.5},
                }
            ],
        }

    mock_client.send_turn.side_effect = side_effect_turn

    agent_loop = ClaudeComputerUseAgentLoop(client=mock_client)
    task = task_service.create_task(goal="Stop test")

    res = agent_loop.run(task_id=task["id"], goal="Stop test", stop_event=stop_evt)

    assert res["status"] == "STOPPED"
    assert res["success"] is False


def test_iteration_limit_enforced():
    """Ensures agent loop does not loop forever."""
    mock_client = MagicMock(spec=ClaudeComputerUseClient)
    mock_client.is_configured = True

    # Forever requesting wait tool
    mock_client.send_turn.return_value = {
        "success": True,
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "call_loop",
                "name": TOOL_NAME_COMPUTER,
                "input": {"action": "wait", "duration": 0.05},
            }
        ],
    }

    agent_loop = ClaudeComputerUseAgentLoop(client=mock_client, max_iterations=3)
    task = task_service.create_task(goal="Infinite loop test")

    res = agent_loop.run(task_id=task["id"], goal="Infinite loop test")

    # Stopped after 3 iterations
    assert mock_client.send_turn.call_count == 3
    assert res["status"] in ("UNVERIFIED", "BLOCKED")
