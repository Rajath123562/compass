"""
Unit tests for ExecutionTraceManager (Phase 6, Capability R, §20, §25).
Verifies detailed execution trace generation and strict redaction of sensitive credentials.
"""

import json

from planner.execution_trace import ExecutionTraceManager


def test_execution_trace_redaction():
    """ExecutionTraceManager redacts Bearer tokens, API keys, and passwords from logs and traces."""
    etm = ExecutionTraceManager()
    dirty_text = "Sent request with Bearer abcdef1234567890 and api_key=sk-11223344556677889900aa with password: mySecretPassword123"
    clean_text = etm.redact_text(dirty_text)

    assert "abcdef1234567890" not in clean_text
    assert "[REDACTED_SECRET]" in clean_text
    assert "sk-11223344556677889900aa" not in clean_text
    assert "[REDACTED_API_KEY]" in clean_text
    assert "mySecretPassword123" not in clean_text
    assert "[REDACTED_PASSWORD]" in clean_text


def test_execution_trace_lifecycle_and_serialization(tmp_path):
    """Initializes, populates, and serializes a full machine-verifiable execution trace."""
    etm = ExecutionTraceManager(trace_dir=tmp_path)
    trace = etm.start_trace("task_trace_1", "Open Notepad and type test")  # noqa: F841

    etm.record_step_start("task_trace_1", "step_1", "Launch Notepad")
    etm.record_step_finish(
        "task_trace_1", "step_1", "COMPLETED", "VERIFIED", "Window observed"
    )

    etm.record_stop_event("task_trace_1", "User stop call")

    out_file = etm.finalize_trace(
        "task_trace_1", "STOPPED", {"final_note": "Stopped cleanly"}
    )
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["task_id"] == "task_trace_1"
    assert data["final_status"] == "STOPPED"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["status"] == "COMPLETED"
    assert len(data["stop_events"]) == 1
