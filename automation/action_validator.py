"""
COMPASS Action Validator
Pre-flight validation pipeline executed before every automation action.

Runs the complete sequence:
  1. Platform check
  2. HWND validity + protected window check
  3. Element revalidation via UIA (element still exists and matches)
  4. Element enabled + visible + bounds check
  5. Control type ↔ action type compatibility
  6. Foreground window context (optional, enabled by default)
  7. Input safety (text length, key allowlist)

Returns ValidationResult(ok, reason) — action proceeds only if ok=True.
"""

from typing import Any

from automation import safety
from automation.models import ValidationResult
from perception import uia_inspector


class ActionValidator:
    """
    Validates an action request before dispatch.
    All checks run in order; first failure short-circuits.
    """

    def __init__(self, check_foreground: bool = True):
        """
        Args:
            check_foreground: If True, verify target is in the foreground window.
                              Can be disabled for special test scenarios.
        """
        self.check_foreground = check_foreground

    def validate_click(self, element_ref: dict[str, Any]) -> ValidationResult:
        """Validate a click action against a resolved element reference."""
        return self._validate_element_action(element_ref, "click")

    def validate_type(self, element_ref: dict[str, Any], text: str) -> ValidationResult:
        """Validate a type action: element + text safety."""
        result = self._validate_element_action(element_ref, "type")
        if not result.ok:
            return result
        return safety.check_text_safe(text)

    def validate_key(self, key_name: str) -> ValidationResult:
        """Validate a keyboard key action."""
        return safety.check_key_safe(key_name)

    def validate_focus(self, element_ref: dict[str, Any]) -> ValidationResult:
        """Validate a focus action."""
        return self._validate_element_action(element_ref, "focus")

    def _validate_element_action(
        self, element_ref: dict[str, Any], action_type: str
    ) -> ValidationResult:
        """Run the full element validation pipeline."""
        hwnd = element_ref.get("hwnd", 0)

        # 1. HWND valid + not a protected system window
        hwnd_check = safety.check_hwnd_safe(hwnd)
        if not hwnd_check.ok:
            return hwnd_check

        # 2. Revalidate via UIA — element must still exist
        revalidation = uia_inspector.revalidate_element(element_ref)
        if not revalidation["valid"]:
            return ValidationResult(
                ok=False,
                reason=f"Element revalidation failed: {revalidation.get('reason', 'unknown')}",
            )

        # Use the fresh element snapshot from revalidation
        fresh_element = revalidation.get("element") or element_ref

        # 3. Enabled, visible, non-zero bounds
        actionable = safety.check_element_actionable(fresh_element)
        if not actionable.ok:
            return actionable

        # 4. Control type ↔ action type
        ct_check = safety.check_control_type_for_action(fresh_element, action_type)
        if not ct_check.ok:
            return ct_check

        # 5. Foreground context check
        if self.check_foreground:
            fg_check = safety.check_foreground_context(hwnd)
            if not fg_check.ok:
                return fg_check

        return ValidationResult(
            ok=True,
            reason="All validation checks passed",
            element_snapshot=fresh_element,
        )


# Module-level default validator
default_validator = ActionValidator(check_foreground=True)
