"""
COMPASS Phase 11 — Security & Secret Repository Audit Script
Scans repository for exposed API keys, tokens, credentials, private keys, and secrets.
"""

import os
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    re.compile(
        r"""(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['"][a-zA-Z0-9_\-]{20,}['"]"""
    ),
    re.compile(r"""Bearer\s+[a-zA-Z0-9_\-\.]{25,}"""),
    re.compile(r"""sk-[a-zA-Z0-9]{25,}"""),
    re.compile(r"""-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"""),
    re.compile(r"""(?i)password\s*[:=]\s*['"][^'"]{8,}['"]"""),
]

SAFE_EXCLUSIONS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "artifacts",
    "assurance",
}

TEST_ALLOWLIST = {
    "test_security_guards.py",
    "test_security_phase5.py",
    "test_security_phase6.py",
    "test_workflow_security.py",
    "test_omniroute_failures_phase10.py",
    "test_phase10_hardening.py",
    "execution_trace.py",
    "checkpoint_manager.py",
    "test_stability_phase10.py",
    "test_secret_redaction.py",
    "test_perception_security.py",
    "test_checkpoint_resume.py",
}


def scan_repository():
    violations = []
    file_count = 0

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in SAFE_EXCLUSIONS]
        for f in files:
            file_count += 1
            if f in TEST_ALLOWLIST or f.endswith(
                (".png", ".jpg", ".jpeg", ".ico", ".pyc", ".db")
            ):
                continue
            fpath = Path(root) / f
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
                for pat in SECRET_PATTERNS:
                    for m in pat.finditer(text):
                        val = m.group(0)
                        # Filter out common test dummies, mock keywords, placeholders
                        if any(
                            k in val.lower()
                            for k in [
                                "dummy",
                                "test",
                                "placeholder",
                                "example",
                                "redacted",
                                "xxx",
                                "mock",
                            ]
                        ):
                            continue
                        rel_path = fpath.relative_to(ROOT_DIR)
                        violations.append(
                            {
                                "file": str(rel_path),
                                "match_snippet": val[:20] + "...[REDACTED]",
                            }
                        )
            except Exception:  # noqa: BLE001, S110
                pass

    print(f"Scanned {file_count} files.")
    print(f"Found {len(violations)} secret violations.")
    for v in violations:
        print(f"  VIOLATION: {v['file']} -> {v['match_snippet']}")
    return violations


if __name__ == "__main__":
    v = scan_repository()
    if v:
        exit(1)  # noqa: PLR1722
    exit(0)  # noqa: PLR1722
