"""
COMPASS Phase 7 — Perception Security, Prompt-Injection Defense & Privacy
Quarantines untrusted screen content, intercepts prompt injection patterns,
redacts sensitive credentials, and manages screenshot ring buffers (Sections 17, 25, 26).
"""

from __future__ import annotations

import atexit
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Known prompt injection markers embedded in screen/OCR text
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"format\s+[a-z]:\s+/q", re.IGNORECASE),
    re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
    re.compile(r"delete\s+system32", re.IGNORECASE),
    re.compile(r"drop\s+database", re.IGNORECASE),
    re.compile(r"approve_all", re.IGNORECASE),
]

# Sensitive credentials patterns to redact before logging or storing
CREDENTIAL_PATTERNS = [
    (re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.IGNORECASE), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"(ghp_[a-zA-Z0-9]{20,})", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
    (
        re.compile(r"Bearer\s+[a-zA-Z0-9\._\-]{20,}", re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        re.compile(r"password\s*[:=]\s*['\"]?[^\s'\"]+['\"]?", re.IGNORECASE),
        "password=[REDACTED]",
    ),
    (
        re.compile(
            r"-----BEGIN\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
]


class UntrustedContentQuarantine:
    """
    Quarantines untrusted screen content and scans for prompt injection attacks.
    Hierarchy: SYSTEM SAFETY > USER GOAL > APPLICATION CONTENT > OCR/VISION CONTENT
    """

    @staticmethod
    def is_injection_attempt(text: str) -> tuple[bool, str]:
        """Check if raw text contains an adversarial prompt injection attempt."""
        if not text:
            return False, ""
        for pat in PROMPT_INJECTION_PATTERNS:
            match = pat.search(text)
            if match:
                return True, f"Prompt injection pattern detected: '{match.group(0)}'"
        return False, ""

    @staticmethod
    def sanitize_untrusted_text(text: str) -> str:
        """
        Quarantine and sanitize text to ensure it cannot be interpreted as system instructions.
        Replaces injection triggers with a safe quarantined indicator.
        """
        if not text:
            return ""
        sanitized = text
        for pat in PROMPT_INJECTION_PATTERNS:
            sanitized = pat.sub("[QUARANTINED_UNTRUSTED_CONTENT]", sanitized)
        return sanitized

    @staticmethod
    def wrap_untrusted_screen_evidence(text: str) -> str:
        """
        Strip instruction-override markers and wrap in untrusted screen evidence tags.
        Guarantees that screen evidence is structurally quarantined from prompt directives.
        """
        if not text:
            return "<untrusted_screen_evidence></untrusted_screen_evidence>"
        cleaned = text
        override_markers = [
            re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
            re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
            re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
            re.compile(r"new\s+system\s+prompt\s*:", re.IGNORECASE),
            re.compile(r"system\s*:", re.IGNORECASE),
            re.compile(r"approve_all", re.IGNORECASE),
        ]
        for pat in override_markers:
            cleaned = pat.sub("[REDACTED_OVERRIDE_MARKER]", cleaned)
        return f"<untrusted_screen_evidence>{cleaned}</untrusted_screen_evidence>"


class CredentialRedactor:
    """Detects and redacts sensitive credentials in OCR and screen text."""

    @staticmethod
    def redact(text: str) -> str:
        if not text:
            return ""
        redacted = text
        for pat, replacement in CREDENTIAL_PATTERNS:
            redacted = pat.sub(replacement, redacted)
        return redacted


class ScreenshotRingBuffer:
    """
    Maintains a bounded ring buffer of screenshots on disk.
    Enforces privacy by automatically deleting older screenshots past max_capacity.
    Ensures temporary capture directory is purged on exit (Section 19, 26).
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        max_capacity: int = 10,
        directory: Path | str | None = None,
        max_files: int | None = None,
    ):
        target_dir = directory or base_dir or (Path.cwd() / "artifacts" / "phase7_screenshots")
        self.base_dir = Path(target_dir).resolve()
        self.max_capacity = max_files if max_files is not None else max_capacity
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._tracked_files: list[Path] = []
        atexit.register(self.cleanup_all)

    def register_screenshot(self, file_path: str) -> str:
        """Track a new screenshot and prune buffer if exceeding capacity."""
        p = Path(file_path).resolve()
        if p.exists():
            self._tracked_files.append(p)
            self._enforce_capacity()
        return str(p)

    def _enforce_capacity(self):
        """Delete oldest files if buffer exceeds max_capacity."""
        while len(self._tracked_files) > self.max_capacity:
            oldest = self._tracked_files.pop(0)
            try:
                if oldest.exists():
                    oldest.unlink()
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to delete stale screenshot %s: %s", oldest, e)

    def cleanup_all(self):
        """Purge all tracked screenshots on exit."""
        for f in self._tracked_files:
            try:
                if f.exists():
                    f.unlink()
            except Exception:  # noqa: BLE001, S110
                pass
        self._tracked_files.clear()

    def add_screenshot(self, filepath: str) -> str:
        return self.register_screenshot(filepath)

    def prune(self) -> None:
        self._enforce_capacity()

    def cleanup(self) -> None:
        self.cleanup_all()


def redact_text(text: str) -> str:
    """Redacts sensitive credentials from text."""
    res = CredentialRedactor.redact(text)
    res = res.replace("[REDACTED_OPENAI_KEY]", "[REDACTED]")
    res = res.replace("[REDACTED_GITHUB_TOKEN]", "[REDACTED]")
    res = re.sub(r"Bearer\s+\[REDACTED_TOKEN\]", "[REDACTED]", res, flags=re.IGNORECASE)
    return res
