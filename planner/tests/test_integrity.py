import os
import tempfile

from planner.reliability.integrity import _calculate_sha256, verify_critical_integrity


def test_verify_critical_integrity():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a valid file
        file1 = os.path.join(temp_dir, "file1.py")
        with open(file1, "wb") as f:
            f.write(b"print('hello')")

        hash1 = _calculate_sha256(file1)

        # Test 1: Valid manifest
        manifest = {"file1.py": hash1}
        is_valid, violations = verify_critical_integrity(manifest, base_dir=temp_dir)
        assert is_valid is True
        assert len(violations) == 0

        # Test 2: Missing file
        manifest = {"file1.py": hash1, "missing.py": "abc12345"}
        is_valid, violations = verify_critical_integrity(manifest, base_dir=temp_dir)
        assert is_valid is False
        assert len(violations) == 1
        assert "MISSING: missing.py" in violations[0]

        # Test 3: Modified file (Hash Mismatch)
        with open(file1, "wb") as f:
            f.write(b"print('hello world')")

        manifest = {"file1.py": hash1}
        is_valid, violations = verify_critical_integrity(manifest, base_dir=temp_dir)
        assert is_valid is False
        assert len(violations) == 1
        assert "MISMATCH: file1.py" in violations[0]
