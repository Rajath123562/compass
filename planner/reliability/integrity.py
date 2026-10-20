import hashlib
import os


def _calculate_sha256(filepath: str) -> str:
    """Calculates the SHA-256 hash of a file."""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_critical_integrity(
    manifest: dict[str, str], base_dir: str = "."
) -> tuple[bool, list[str]]:
    """
    Verifies the integrity of critical files against a trusted manifest.

    Args:
        manifest: Dictionary mapping relative file paths to their expected SHA-256 hashes.
        base_dir: Base directory to resolve file paths against.

    Returns:
        (is_valid, list_of_violations)
    """
    violations = []

    for relative_path, expected_hash in manifest.items():
        filepath = os.path.join(base_dir, relative_path)

        if not os.path.exists(filepath):
            violations.append(f"MISSING: {relative_path}")
            continue

        try:
            actual_hash = _calculate_sha256(filepath)
            if actual_hash != expected_hash:
                violations.append(
                    f"MISMATCH: {relative_path} (expected {expected_hash}, got {actual_hash})"
                )
        except Exception as e:  # noqa: BLE001
            violations.append(f"ERROR: {relative_path} ({e!s})")

    return (len(violations) == 0, violations)
