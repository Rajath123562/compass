"""
COMPASS Phase 4 — Deterministic Security Guards
Enforces absolute rejection of arbitrary system command execution (PowerShell, CMD, Python, shell, rm).
Quarantines untrusted screen content and defends against prompt injection.
Maintains instruction hierarchy: SYSTEM SAFETY > USER GOAL > SCREEN CONTENT.
"""

from __future__ import annotations

import re

from backend.app.logging_config import logger
from planner.models import Decision, PlannedAction, PlannerActionType
from planner.risk_classifier import canonicalize_command_string


class SecurityGuard:
    """
    Deterministic security gate enforcing zero direct OS command execution.
    """

    DISALLOWED_COMMAND_REGEX = re.compile(
        r"""\b(
            powershell(\.exe)? |
            cmd(\.exe)? |
            pwsh(\.exe)? |
            python(\.exe)? |
            bash(\.exe)? |
            sh(\.exe)? |
            wscript(\.exe)? |
            cscript(\.exe)? |
            mshta(\.exe)? |
            reg(\.exe)? |
            regedit(\.exe)? |
            vssadmin |
            certutil |
            bitsadmin |
            rundll32 |
            taskkill |
            format\s+[a-zA-Z]: |
            (del|rm|rmdir)\s+[\/\-] |
            invoke-expression |
            iex\b |
            downloadstring
        )\b""",
        re.IGNORECASE | re.VERBOSE,
    )

    PROMPT_INJECTION_PATTERNS = [  # noqa: RUF012
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|compass|system|safety)?\s*(instructions|rules|prompts|safety)",
            re.IGNORECASE,
        ),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"override\s+(all\s+)?(safety|security|system|restrictions)?", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"jailbreak|dan\s+mode", re.IGNORECASE),
        re.compile(r"forget\s+all\s+(previous|prior)?\s*instructions", re.IGNORECASE),
        re.compile(r"delete\s+(all\s+)?(the\s+)?(user'?s?\s+)?files", re.IGNORECASE),
        re.compile(r"execute\s+(powershell|cmd|sh|bash|rm|del)", re.IGNORECASE),
        re.compile(r"bypass\s+(approval|safety|security|confirmation)", re.IGNORECASE),
    ]

    def __init__(self):
        pass

    def validate_action_security(
        self, action: PlannedAction
    ) -> tuple[bool, str | None]:
        """
        Validate that a planned action from the model does not attempt arbitrary OS execution.
        """
        # 1. Action type allowlist check
        if action.action_type not in PlannerActionType:
            return (
                False,
                f"Action type '{action.action_type}' is not an allowlisted GUI action.",
            )

        # 2. Check parameters for arbitrary command strings
        for param_key, param_val in action.parameters.items():
            str_val = str(param_val)
            canon_val = canonicalize_command_string(str_val)
            if "[suspicious_encoded_command]" in canon_val:
                return (
                    False,
                    f"Arbitrary command execution forbidden. Obfuscated or malformed Base64 encoded command detected in '{param_key}'.",
                )
            if self.DISALLOWED_COMMAND_REGEX.search(str_val) or self.DISALLOWED_COMMAND_REGEX.search(canon_val):
                match = (
                    self.DISALLOWED_COMMAND_REGEX.search(canon_val)
                    or self.DISALLOWED_COMMAND_REGEX.search(str_val)
                ).group(0)
                logger.error(
                    f"SecurityGuard REJECTED arbitrary command attempt in parameter '{param_key}': {match}"
                )
                return (
                    False,
                    f"Arbitrary command execution forbidden. Detected prohibited pattern: '{match}'.",
                )

        # 3. Check target description
        target_canon = canonicalize_command_string(action.target_description)
        if "[suspicious_encoded_command]" in target_canon:
            return (
                False,
                "Arbitrary command execution forbidden. Obfuscated Base64 encoded command detected in target description.",
            )
        if self.DISALLOWED_COMMAND_REGEX.search(action.target_description) or self.DISALLOWED_COMMAND_REGEX.search(target_canon):
            match = (
                self.DISALLOWED_COMMAND_REGEX.search(target_canon)
                or self.DISALLOWED_COMMAND_REGEX.search(action.target_description)
            ).group(0)
            logger.error(
                f"SecurityGuard REJECTED command attempt in target description: {match}"
            )
            return (
                False,
                f"Arbitrary command execution forbidden. Detected prohibited pattern: '{match}'.",
            )

        return True, "Security validation passed"

    def validate_decision_security(
        self, decision: Decision
    ) -> tuple[bool, str | None]:
        """
        Validate that a Decision does not attempt arbitrary command execution.
        """
        # Check action
        if decision.action not in PlannerActionType:
            return False, f"Decision action '{decision.action}' is forbidden."

        # Check parameters
        for param_key, param_val in decision.parameters.items():  # noqa: PERF102
            str_val = str(param_val)
            canon_val = canonicalize_command_string(str_val)
            if "[suspicious_encoded_command]" in canon_val:
                return (
                    False,
                    f"Arbitrary command execution forbidden. Obfuscated or malformed Base64 encoded command detected in '{param_key}'.",
                )
            if self.DISALLOWED_COMMAND_REGEX.search(str_val) or self.DISALLOWED_COMMAND_REGEX.search(canon_val):
                match = (
                    self.DISALLOWED_COMMAND_REGEX.search(canon_val)
                    or self.DISALLOWED_COMMAND_REGEX.search(str_val)
                ).group(0)
                return (
                    False,
                    f"Arbitrary command execution forbidden: prohibited pattern '{match}'.",
                )

        # Check target description
        target_canon = canonicalize_command_string(decision.target_description)
        if "[suspicious_encoded_command]" in target_canon:
            return (
                False,
                "Arbitrary command execution forbidden. Obfuscated Base64 encoded command detected in target description.",
            )
        if self.DISALLOWED_COMMAND_REGEX.search(decision.target_description) or self.DISALLOWED_COMMAND_REGEX.search(target_canon):
            match = (
                self.DISALLOWED_COMMAND_REGEX.search(target_canon)
                or self.DISALLOWED_COMMAND_REGEX.search(decision.target_description)
            ).group(0)
            return (
                False,
                f"Arbitrary command execution forbidden: prohibited pattern '{match}'.",
            )

        return True, "Decision security validation passed"

    def sanitize_untrusted_screen_content(self, screen_text: str) -> tuple[str, bool]:
        """
        Quarantine and sanitize untrusted screen text to prevent prompt injection.
        Returns: (sanitized_text, was_injection_detected)
        """
        if not screen_text:
            return "", False

        cleaned = screen_text
        detected = False

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if pattern.search(cleaned):
                detected = True
                cleaned = pattern.sub(
                    "[UNTRUSTED_INJECTION_ATTEMPT_QUARANTINED]", cleaned
                )
                logger.warning(
                    "SecurityGuard: Prompt injection pattern detected in screen content and quarantined."
                )

        return cleaned, detected


security_guard = SecurityGuard()
