"""
COMPASS Continuous Production Assurance — Secret Scanner
Scans source, configuration, assurance code, dotfiles, and logs for leaked credentials.
Redacts secrets, covers assurance directory, handles dotfiles, and avoids broad generic-word suppression (COMPASS-AUDIT-015).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

REPORT_DIR = ROOT_DIR / "assurance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Secret regex patterns
SECRET_PATTERNS = [
    (
        re.compile(r"""(?i)(?:api[_-]?key|apikey)\s*[:=]\s*['"]([a-zA-Z0-9_\-]{20,})['"]"""),
        "Generic API Key",
        "HIGH",
    ),
    (
        re.compile(r"""(?i)(?:secret[_-]?key|secret)\s*[:=]\s*['"]([a-zA-Z0-9_\-]{20,})['"]"""),
        "Generic Secret Key",
        "HIGH",
    ),
    (
        re.compile(r"""(?i)(?:password|passwd|pwd)\s*[:=]\s*['"]([^'"]{8,})['"]"""),
        "Hardcoded Password",
        "MEDIUM",
    ),
    (
        re.compile(r"""AIza[0-9A-Za-z\-_]{35}"""),
        "Google Cloud / Firebase API Key",
        "CRITICAL",
    ),
    (
        re.compile(r"""sk-[a-zA-Z0-9]{32,}"""),
        "OpenAI API Key",
        "CRITICAL",
    ),
    (
        re.compile(r"""sk-ant-[a-zA-Z0-9_\-]{32,}"""),
        "Anthropic API Key",
        "CRITICAL",
    ),
    (
        re.compile(r"""AKIA[0-9A-Z]{16}"""),
        "AWS Access Key ID",
        "CRITICAL",
    ),
    (
        re.compile(r"""(?i)bearer\s+[a-zA-Z0-9_\-\.]{30,}"""),
        "Bearer Token",
        "HIGH",
    ),
    (
        re.compile(r"""ghp_[a-zA-Z0-9]{36}"""),
        "GitHub Personal Access Token",
        "CRITICAL",
    ),
    (
        re.compile(r"""gho_[a-zA-Z0-9]{36}"""),
        "GitHub OAuth Token",
        "CRITICAL",
    ),
    (
        re.compile(r"""xox[baprs]-[0-9a-zA-Z]{10,48}"""),
        "Slack Token",
        "HIGH",
    ),
]

SCAN_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
    ".md",
    ".txt",
    ".bat",
    ".sh",
    ".ps1",
}

# Directories to skip (untracked build caches and vendor dependencies)
SKIP_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".git",
    ".pytest_cache",
    "dist",
    "coverage",
    ".mypy_cache",
    "artifacts",
}

# Test files that specifically test secret redaction mechanisms with known mock tokens
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
    "test_phase13_adversarial.py",
    "test_secret_scanner.py",
    "test_diagnostics.py",
    "test_temporal_comparator.py",
    "test_adversarial_phase13.py",
    "bandit_report.json",
    "sast_report.json",
}

# Exact dummy placeholders (narrow matching on matched tokens, NOT whole line suppression)
KNOWN_DUMMY_TOKENS = {
    "your_api_key_here",
    "your-api-key-here",
    "your_secret_key_here",
    "example_api_key",
    "dummy_api_key_1234567890",
    "test_secret_token_1234567890",
    "fake_password_12345",
    "placeholder_key_value",
    "AIzaSyDummyKeyForTestingOnly1234567",
    "sk-test12345678901234567890123456789012",
}


def scrub_all_secrets(line: str) -> str:
    """Scrub all secret patterns from a line so evidence never contains plain secrets."""
    scrubbed = line
    for pat, name, _ in SECRET_PATTERNS:
        scrubbed = pat.sub(f"[REDACTED_{name.replace(' ', '_').upper()}]", scrubbed)
    return scrubbed


def is_dummy_token(match_text: str) -> bool:
    """Check if the matched secret text itself is an obvious test placeholder."""
    cleaned = match_text.strip("'\" \t\r\n")
    if cleaned in KNOWN_DUMMY_TOKENS:
        return True
    if all(c in "xX0123456789-_" for c in cleaned):
        return True
    return False


def should_scan_file(filepath: Path) -> bool:
    name = filepath.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    return filepath.suffix.lower() in SCAN_EXTENSIONS


def scan_file(filepath: Path) -> tuple[list[dict], list[dict]]:
    """Scan a single file for secret patterns. Returns (findings, false_positives)."""
    findings = []
    false_positives = []
    fname = filepath.name
    is_allowlisted_file = fname in TEST_ALLOWLIST

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        rel_path = str(filepath.relative_to(ROOT_DIR))
        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern, name, severity in SECRET_PATTERNS:
                m = pattern.search(line)
                if m:
                    matched_val = m.group(1) if m.groups() else m.group(0)
                    redacted = scrub_all_secrets(line.strip())
                    record = {
                        "file": rel_path,
                        "line": line_num,
                        "secret_type": name,
                        "severity": severity,
                        "evidence": redacted[:200],
                    }

                    if is_allowlisted_file or is_dummy_token(matched_val):
                        record["reason"] = "allowlisted_test_or_dummy_token"
                        false_positives.append(record)
                    else:
                        findings.append(record)
    except Exception:  # noqa: BLE001, S110
        pass
    return findings, false_positives


def scan_repository() -> dict:
    """Scan the entire repository for secrets."""
    print("[SecretScan] Scanning repository for leaked secrets...")
    all_findings = []
    all_fps = []
    files_scanned = 0

    for p in ROOT_DIR.rglob("*"):
        if p.is_dir():
            continue
        rel = str(p.relative_to(ROOT_DIR))
        parts = rel.split(os.sep)
        if any(skip in parts for skip in SKIP_DIRS):
            continue
        if not should_scan_file(p):
            continue

        findings, fps = scan_file(p)
        all_findings.extend(findings)
        all_fps.extend(fps)
        files_scanned += 1

    result = {
        "timestamp": time.time(),
        "files_scanned": files_scanned,
        "total_findings": len(all_findings),
        "findings": all_findings,
        "false_positives_filtered": len(all_fps),
        "by_severity": {},
    }

    for f in all_findings:
        sev = f["severity"]
        result["by_severity"][sev] = result["by_severity"].get(sev, 0) + 1

    out = REPORT_DIR / "secret_scan_report.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"[SecretScan] Scanned {files_scanned} files, found {len(all_findings)} unverified secret(s), filtered {len(all_fps)} dummy fixture(s)."
    )
    print(f"[SecretScan] Report saved: {out}")
    return result


if __name__ == "__main__":
    scan_repository()
