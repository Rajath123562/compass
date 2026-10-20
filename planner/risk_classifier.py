"""
COMPASS Phase 4 — Contextual Risk Classifier
Deterministic safety engine that classifies action risk based on action type,
target identity, target label, application context, reversibility, and data loss potential.
High-risk actions unconditionally mandate explicit user confirmation.
"""

from __future__ import annotations

import base64
import re
from typing import Any

from pydantic import BaseModel, Field

from backend.app.logging_config import logger
from planner.models import PlannerActionType, RiskLevel

HIGH_RISK_PATTERNS = [
    r"\b(rm|del|erase|rmdir|rd|remove-item|ri|unlink)\b",
    r"\b(kill|taskkill|stop-process|spps)\b",
    r"\b(reg|regedit|new-itemproperty|set-itemproperty|remove-itemproperty)\b",
    r"\b(format|format-volume|diskpart|bcdedit|vssadmin|cipher)\b",
    r"\b(sc|new-service|set-service|wmic|netsh|icacls|takeown)\b",
    r"\b(iex|invoke-expression|invoke-webrequest|iwr|curl|wget|start-bitstransfer)\b",
    r"\b(drop\s+table|truncate\s+table|delete\s+from)\b",
]

ENCODED_CMD_REGEX = re.compile(
    r"(?:^|\s)-(?:e|ec|enc|encodedcommand)\s+([A-Za-z0-9+/=]{8,})",
    re.IGNORECASE,
)


def canonicalize_command_string(raw: str) -> str:
    """Canonicalize command strings by removing shell escapes and unmasking encoded payloads."""
    if not raw:
        return ""
    cleaned = raw.replace("`", "").replace("^", "").replace('""', "").replace("''", "")
    match = ENCODED_CMD_REGEX.search(cleaned)
    if match:
        try:
            decoded_bytes = base64.b64decode(match.group(1), validate=False)
            decoded_text = (
                decoded_bytes.decode("utf-16le", errors="ignore")
                or decoded_bytes.decode("utf-8", errors="ignore")
            )
            cleaned = f"{cleaned} [DECODED_PAYLOAD: {decoded_text}]"
        except Exception:
            cleaned = f"{cleaned} [SUSPICIOUS_ENCODED_COMMAND]"
    return " ".join(cleaned.lower().split())


def is_consequential_command(
    action_type: Any, target: str, params: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """Inspect action type, target and parameters for high-risk / consequential operations."""
    p = params or {}
    act_str = action_type.value if hasattr(action_type, "value") else str(action_type or "")
    combined = canonicalize_command_string(
        f"{act_str} {target} {p.get('command', '')} {p.get('script', '')} "
        f"{p.get('path', '')} {p.get('url', '')} {p.get('text', '')}"
    )
    if "[suspicious_encoded_command]" in combined:
        return True, "Obfuscated or malformed Base64 encoded command detected"
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return True, f"Matched high-risk operational pattern: {pattern}"
    if ".." in str(p.get("path", "")) or ".." in str(target):
        return True, "Path traversal sequence ('..') detected in target/path"
    url = str(p.get("url", "") or target).strip().lower()
    if url.startswith(("file://", "javascript:", "vbscript:", "data:text/html")):
        return True, f"Restricted URI scheme detected: {url[:24]}"
    return False, "Standard operation"



class RiskClassification(BaseModel):
    """Result of contextual risk classification."""

    risk_level: RiskLevel
    requires_confirmation: bool
    reasons: list[str] = Field(default_factory=list)
    is_reversible: bool = True
    data_loss_potential: bool = False
    side_effect_potential: bool = False


class RiskClassifier:
    """
    Deterministic risk classification layer.
    The AI model NEVER decides whether its own proposed action is safe.
    """

    HIGH_RISK_DESTRUCTIVE_KEYWORDS = [  # noqa: RUF012
        "delete",
        "remove",
        "erase",
        "format",
        "drop",
        "truncate",
        "destroy",
        "wipe",
        "uninstall",
        "purge",
        "clear all",
        "discard",
        "overwrite",
        "replace",
    ]

    HIGH_RISK_EXIT_KEYWORDS = [  # noqa: RUF012
        "close",
        "exit",
        "quit",
        "kill",
        "terminate",
        "shutdown",
        "reboot",
        "restart",
    ]

    HIGH_RISK_EXTERNAL_SIDE_EFFECTS = [  # noqa: RUF012
        "submit",
        "publish",
        "send",
        "checkout",
        "purchase",
        "pay",
        "order",
        "transfer",
        "execute",
        "apply",
        "commit",
        "push",
    ]

    HIGH_RISK_SENSITIVE_TARGETS = [  # noqa: RUF012
        "password",
        "secret",
        "token",
        "credential",
        "api key",
        "pin",
        "license",
    ]

    DESTRUCTIVE_KEY_COMBINATIONS = [  # noqa: RUF012
        "alt+f4",
        "ctrl+w",
        "shift+delete",
        "ctrl+q",
        "ctrl+alt+del",
    ]

    HARMLESS_MENU_KEYWORDS = [  # noqa: RUF012
        "menu",
        "open menu",
        "view",
        "help",
        "about",
        "file",
        "edit",
        "format",
        "window",
        "options",
        "tools",
        "navigate",
        "tab",
        "expand",
        "collapse",
        "scroll",
        "maximize",
        "minimize",
    ]

    # Pre-compiled high-performance pattern matchers
    _DESTRUCTIVE_PATTERN = re.compile(
        r"\b("
        + "|".join(re.escape(k) for k in HIGH_RISK_DESTRUCTIVE_KEYWORDS)
        + r")\b",
        re.IGNORECASE,
    )
    _EXIT_PATTERN = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in HIGH_RISK_EXIT_KEYWORDS) + r")\b",
        re.IGNORECASE,
    )
    _EXTERNAL_PATTERN = re.compile(
        r"\b("
        + "|".join(re.escape(k) for k in HIGH_RISK_EXTERNAL_SIDE_EFFECTS)
        + r")\b",
        re.IGNORECASE,
    )

    def __init__(self):
        pass

    def classify_risk(
        self,
        action: PlannerActionType,
        target_name: str = "",
        target_control_type: str = "",
        parameters: dict[str, Any] | None = None,
        application_name: str = "",
        window_title: str = "",
    ) -> RiskClassification:
        """
        Classify risk deterministically based on full context.
        """
        params = parameters or {}
        target_label = (target_name or "").lower().strip()
        control_type = (target_control_type or "").lower().strip()
        app = (application_name or "").lower().strip()  # noqa: F841
        title = (window_title or "").lower().strip()  # noqa: F841

        reasons = []
        is_reversible = True
        data_loss_potential = False
        side_effect_potential = False
        elevated_to_high = False

        # 0. Canonical command and high-risk pattern check across parameters/targets
        is_consequential, consequential_reason = is_consequential_command(
            action, target_name, params
        )
        if is_consequential:
            reasons.append(consequential_reason)
            elevated_to_high = True
            is_reversible = False
            data_loss_potential = True
            side_effect_potential = True

        # 1. Non-interactive or purely visual actions (if not carrying consequential command): unconditionally LOW
        if not elevated_to_high and action in [
            PlannerActionType.OBSERVE,
            PlannerActionType.HIGHLIGHT,
            PlannerActionType.WAIT,
        ]:
            return RiskClassification(
                risk_level=RiskLevel.LOW,
                requires_confirmation=False,
                reasons=[f"Action '{action.value}' is non-invasive and read-only."],
                is_reversible=True,
                data_loss_potential=False,
                side_effect_potential=False,
            )

        # 2. Key combination analysis
        if action == PlannerActionType.KEY_COMBINATION:
            combo = (
                str(params.get("combination") or params.get("keys") or "")
                .lower()
                .strip()
            )
            combo_normalized = combo.replace(" ", "")
            for destructive_combo in self.DESTRUCTIVE_KEY_COMBINATIONS:
                if destructive_combo in combo_normalized:
                    reasons.append(
                        f"Destructive key combination '{combo}' can close applications or bypass recycle bin."
                    )
                    elevated_to_high = True
                    is_reversible = False
                    data_loss_potential = True
                    break

        # 3. Sensitive / Credential field interaction
        for sens_kw in self.HIGH_RISK_SENSITIVE_TARGETS:
            if sens_kw in target_label or control_type == "password":
                reasons.append(
                    f"Target '{target_name}' involves sensitive credentials or authentication."
                )
                elevated_to_high = True
                side_effect_potential = True
                break

        # 4. Destructive keyword analysis on target label
        m_dest = self._DESTRUCTIVE_PATTERN.search(target_label)
        if m_dest:
            dest_kw = m_dest.group(1).lower()
            reasons.append(
                f"Target '{target_name}' contains destructive keyword '{dest_kw}'."
            )
            elevated_to_high = True
            is_reversible = False
            data_loss_potential = True

        # 5. Application termination keywords on target
        if not elevated_to_high:
            m_exit = self._EXIT_PATTERN.search(target_label)
            if m_exit:
                exit_kw = m_exit.group(1).lower()
                reasons.append(
                    f"Target '{target_name}' contains application termination keyword '{exit_kw}'."
                )
                elevated_to_high = True
                is_reversible = False

        # 6. External side effect keywords
        if not elevated_to_high:
            m_ext = self._EXTERNAL_PATTERN.search(target_label)
            if m_ext:
                ext_kw = m_ext.group(1).lower()
                reasons.append(
                    f"Target '{target_name}' triggers external side effect ('{ext_kw}')."
                )
                elevated_to_high = True
                side_effect_potential = True
                is_reversible = False

        # If elevated to HIGH, return immediately
        if elevated_to_high:
            logger.info(
                f"RiskClassifier classified action '{action.value}' on '{target_name}' as HIGH: {reasons}"
            )
            return RiskClassification(
                risk_level=RiskLevel.HIGH,
                requires_confirmation=True,  # Mandatory per Directive §9 & Addendum §6
                reasons=reasons,
                is_reversible=is_reversible,
                data_loss_potential=data_loss_potential,
                side_effect_potential=side_effect_potential,
            )

        # 7. Check for Harmless menu / navigation targets -> LOW
        for menu_kw in self.HARMLESS_MENU_KEYWORDS:
            if menu_kw in target_label:
                reasons.append(
                    f"Target '{target_name}' is a harmless navigation or display element."
                )
                return RiskClassification(
                    risk_level=RiskLevel.LOW,
                    requires_confirmation=False,
                    reasons=reasons,
                    is_reversible=True,
                    data_loss_potential=False,
                    side_effect_potential=False,
                )

        # 7b. Check for uncertain or ambiguous targets (§10 Risk Uncertainty)
        if any(
            kw in target_label
            for kw in [
                "uncertain",
                "ambiguous",
                "unidentified",
                "unrecognized",
                "raw_target",
            ]
        ):
            reasons.append(
                f"Target '{target_name}' context is uncertain; requiring confirmation under zero-trust policy."
            )
            return RiskClassification(
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                reasons=reasons,
                is_reversible=False,
                data_loss_potential=False,
                side_effect_potential=True,
            )

        # 8. Standard clicking, typing, scrolling -> MEDIUM
        if action in [
            PlannerActionType.TYPE,
            PlannerActionType.CLICK,
            PlannerActionType.DOUBLE_CLICK,
            PlannerActionType.RIGHT_CLICK,
        ]:
            reasons.append(f"Action '{action.value}' modifies user workspace state.")
            return RiskClassification(
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=False,  # Can execute in ASSIST/AUTONOMOUS, asks in CONFIRM
                reasons=reasons,
                is_reversible=True,
                data_loss_potential=False,
                side_effect_potential=False,
            )

        # Default fallback: LOW
        return RiskClassification(
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            reasons=["Standard non-destructive action."],
            is_reversible=True,
            data_loss_potential=False,
            side_effect_potential=False,
        )


risk_classifier = RiskClassifier()
