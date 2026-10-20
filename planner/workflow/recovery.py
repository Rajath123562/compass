import hashlib
import hmac
import json
import os
from typing import Any


class CheckpointCorruptedError(Exception):
    pass


class CheckpointManager:
    """Manages Write-Ahead Log (WAL) checkpoints with HMAC integrity verification."""

    def __init__(self, secret_key: bytes, wal_dir: str):
        self.secret_key = secret_key
        self.wal_dir = wal_dir
        os.makedirs(self.wal_dir, exist_ok=True)

    def _get_path(self, workflow_id: str) -> str:
        return os.path.join(self.wal_dir, f"{workflow_id}.wal")

    def _generate_hmac(self, data: bytes) -> str:
        return hmac.new(self.secret_key, data, hashlib.sha256).hexdigest()

    def save_checkpoint(self, workflow_id: str, state_dict: dict[str, Any]):
        """Serializes the state dictionary, signs it, and saves to WAL."""
        payload_str = json.dumps(state_dict, sort_keys=True)
        payload_bytes = payload_str.encode("utf-8")
        signature = self._generate_hmac(payload_bytes)

        envelope = {"payload": state_dict, "signature": signature}

        path = self._get_path(workflow_id)
        # Write to a temporary file then rename for atomic updates
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        # Atomic replace
        os.replace(temp_path, path)

    def load_checkpoint(self, workflow_id: str) -> dict[str, Any] | None:
        """Loads a checkpoint from WAL, verifying the HMAC signature."""
        path = self._get_path(workflow_id)
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            try:
                envelope = json.load(f)
            except json.JSONDecodeError:
                raise CheckpointCorruptedError("Checkpoint is not valid JSON")

        if "payload" not in envelope or "signature" not in envelope:
            raise CheckpointCorruptedError("Checkpoint missing payload or signature")

        state_dict = envelope["payload"]
        stored_signature = envelope["signature"]

        payload_str = json.dumps(state_dict, sort_keys=True)
        expected_signature = self._generate_hmac(payload_str.encode("utf-8"))

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(stored_signature, expected_signature):
            raise CheckpointCorruptedError(
                "Checkpoint HMAC signature verification failed"
            )

        return state_dict

    def clear_checkpoint(self, workflow_id: str):
        """Removes a WAL file once a workflow completes successfully."""
        path = self._get_path(workflow_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


# Re-export Phase 4 recovery engine symbols
from planner.recovery_engine import *  # noqa: F401, F403
