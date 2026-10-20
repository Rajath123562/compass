"""
Unit tests for CheckpointManager (Phase 6, Capability L, M, §14, §17, §18).
Verifies HMAC authentication, secret redaction, tamper detection,
and safe desktop revalidation before resuming.
"""

import json

from planner.checkpoint_manager import CheckpointManager


def test_checkpoint_save_and_load_integrity(tmp_path):
    """Saves authenticated checkpoint and successfully verifies HMAC signature on load."""
    cm = CheckpointManager(storage_dir=tmp_path)
    cp = cm.save_checkpoint(
        task_id="task_cp_1",
        step_id="step_2",
        completed_step_ids=["step_1"],
        verified_state={"window": "Notepad", "text_verified": True},
        current_app="Notepad",
        expected_window_title="Untitled - Notepad",
    )

    assert cp.signature is not None
    assert len(cp.signature) == 64

    ok, loaded_cp, err = cm.load_checkpoint("task_cp_1", "step_2")  # noqa: RUF059
    assert ok is True
    assert loaded_cp.task_id == "task_cp_1"
    assert loaded_cp.completed_step_ids == ["step_1"]


def test_checkpoint_tamper_detection(tmp_path):
    """Tampering with saved checkpoint JSON causes HMAC verification failure."""
    cm = CheckpointManager(storage_dir=tmp_path)
    cm.save_checkpoint(
        task_id="task_tamper",
        step_id="step_1",
        completed_step_ids=[],
        verified_state={"balance": 100},
    )

    # Tamper with the saved file
    cp_file = tmp_path / "task_tamper_step_1.json"
    content = cp_file.read_text(encoding="utf-8")
    tampered_content = content.replace("100", "999999")
    cp_file.write_text(tampered_content, encoding="utf-8")

    ok, loaded_cp, err = cm.load_checkpoint("task_tamper", "step_1")  # noqa: RUF059
    assert ok is False
    assert "integrity validation failed" in err.lower()


def test_checkpoint_secret_redaction(tmp_path):
    """Credentials, tokens, and passwords in state are automatically redacted."""
    cm = CheckpointManager(storage_dir=tmp_path)
    cp = cm.save_checkpoint(
        task_id="task_secrets",
        step_id="step_1",
        completed_step_ids=[],
        verified_state={
            "api_key": "sk-123456789012345678901234",
            "password": "super_secret_password",
            "auth_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "regular_info": "safe_data",
        },
    )

    state = cp.verified_state
    assert state["api_key"] == "[REDACTED_SECRET]"
    assert state["password"] == "[REDACTED_SECRET]"
    assert "[REDACTED_SECRET]" in state["auth_header"]
    assert state["regular_info"] == "safe_data"


def test_checkpoint_validate_for_resume_desktop_context(tmp_path):
    """Safe resume succeeds only if live desktop window matches expected window title."""
    cm = CheckpointManager(storage_dir=tmp_path)
    cp = cm.save_checkpoint(
        task_id="task_resume",
        step_id="step_1",
        completed_step_ids=[],
        verified_state={},
        expected_window_title="Notepad",
    )

    # Match
    ok, _ = cm.validate_for_resume(cp, {"title": "Untitled - Notepad"})
    assert ok is True

    # Mismatch
    ok, err = cm.validate_for_resume(cp, {"title": "Calculator"})
    assert ok is False
    assert "Desktop context mismatch" in err


def test_multimodal_checkpoint_integrity_and_corruption(tmp_path):
    """Verify multimodal checkpoint fields are signed with HMAC and corruption is detected."""
    cm = CheckpointManager(storage_dir=tmp_path)
    cp = cm.save_checkpoint(  # noqa: F841
        task_id="task_mm_cp",
        step_id="step_mm_1",
        completed_step_ids=["step_0"],
        verified_state={"count": 1},
        observation_id="obs_999",
        evidence_ids=["ev_1", "ev_2"],
        evidence_fingerprint="sha256_abcdef",
        perception_state="CONSISTENT",
        monitor_dpi_context={"dpi": 1.25, "monitor_id": 0},
    )

    # Valid load
    ok, loaded_cp, err = cm.load_checkpoint("task_mm_cp", "step_mm_1")
    assert ok is True
    assert loaded_cp.observation_id == "obs_999"
    assert loaded_cp.evidence_fingerprint == "sha256_abcdef"
    assert loaded_cp.monitor_dpi_context["dpi"] == 1.25

    # Corrupt multimodal field
    cp_file = tmp_path / "task_mm_cp_step_mm_1.json"
    with open(cp_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["evidence_fingerprint"] = "tampered_fingerprint"
    with open(cp_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Corrupted load must fail HMAC validation
    ok, bad_cp, err = cm.load_checkpoint("task_mm_cp", "step_mm_1")  # noqa: RUF059
    assert ok is False
    assert "HMAC mismatch" in err
