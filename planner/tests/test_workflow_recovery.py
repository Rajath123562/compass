import json
import os
import tempfile

import pytest

from planner.workflow.recovery import CheckpointCorruptedError, CheckpointManager


def test_checkpoint_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CheckpointManager(secret_key=b"super_secret", wal_dir=tmpdir)

        wf_id = "wf123"
        state = {"nodes_completed": ["A", "B"], "variables": {"user": "test"}}

        cm.save_checkpoint(wf_id, state)

        loaded_state = cm.load_checkpoint(wf_id)
        assert loaded_state == state


def test_checkpoint_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CheckpointManager(secret_key=b"super_secret", wal_dir=tmpdir)
        assert cm.load_checkpoint("non_existent") is None


def test_checkpoint_tampering():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CheckpointManager(secret_key=b"super_secret", wal_dir=tmpdir)

        wf_id = "wf_tampered"
        state = {"status": "PAUSED"}
        cm.save_checkpoint(wf_id, state)

        # Tamper the file manually
        path = cm._get_path(wf_id)
        with open(path, "r", encoding="utf-8") as f:
            envelope = json.load(f)

        # Change the payload without updating the signature
        envelope["payload"]["status"] = "COMPLETED"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        # Loading should fail due to signature mismatch
        with pytest.raises(
            CheckpointCorruptedError, match="HMAC signature verification failed"
        ):
            cm.load_checkpoint(wf_id)


def test_checkpoint_clear():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CheckpointManager(secret_key=b"super_secret", wal_dir=tmpdir)
        wf_id = "wf_clear"

        cm.save_checkpoint(wf_id, {"data": 1})
        assert os.path.exists(cm._get_path(wf_id))

        cm.clear_checkpoint(wf_id)
        assert not os.path.exists(cm._get_path(wf_id))
