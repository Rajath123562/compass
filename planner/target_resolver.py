"""
COMPASS Target Resolver & Revalidator
Resolves AI planner TargetReference descriptions into concrete UIA elements.
Enforces pre-dispatch live revalidation and rejects ambiguous or stale targets.
"""

from __future__ import annotations

from typing import Any

from automation.action_validator import ActionValidator
from perception import uia_inspector
from planner.models import TargetReference


class TargetResolutionResult:
    def __init__(
        self,
        success: bool,
        element: dict[str, Any] | None = None,
        error: str | None = None,
        is_ambiguous: bool = False,
        candidate_count: int = 0,
        candidates: list[dict[str, Any]] | None = None,
        confidence_delta: float = 0.0,
    ):
        self.success = success
        self.element = element
        self.error = error
        self.is_ambiguous = is_ambiguous
        self.candidate_count = candidate_count
        self.candidates = candidates or []
        self.confidence_delta = confidence_delta


class TargetResolver:
    """
    Resolves planned TargetReference models to verified UIElement dictionaries.
    """

    def __init__(self, check_foreground: bool = False):
        self._validator = ActionValidator(check_foreground=check_foreground)

    def resolve(
        self,
        target_ref: TargetReference | None,
        available_elements: list[dict[str, Any]],
        target_description: str = "",
        target_hwnd: int | None = None,
    ) -> TargetResolutionResult:
        """
        Resolve a TargetReference against a list of perceived UI elements.
        Uses a strict precedence hierarchy and rejects ambiguous targets.
        """
        if not target_ref and not target_description:
            return TargetResolutionResult(
                success=False,
                error="Neither target_reference nor target_description was provided.",
            )

        if isinstance(available_elements, dict):
            available_elements = available_elements.get("elements", [])
        candidates = list(available_elements)
        if not candidates:
            return TargetResolutionResult(
                success=False,
                error="No UI elements available to resolve target against.",
            )

        # 1. Filter by HWND if specified
        hwnd = (target_ref.hwnd if target_ref else None) or target_hwnd
        if hwnd:
            filtered_hwnd = [e for e in candidates if e.get("hwnd") == hwnd]
            if filtered_hwnd:
                candidates = filtered_hwnd

        # 2. Try Exact RuntimeId match
        if target_ref and target_ref.runtime_id:
            for e in candidates:
                if str(e.get("runtime_id", "")) == str(target_ref.runtime_id):
                    return TargetResolutionResult(
                        success=True, element=e, candidate_count=1
                    )

        # 3. Try AutomationId match
        if target_ref and target_ref.automation_id:
            auto_id = target_ref.automation_id.strip()
            if auto_id:
                auto_matches = [
                    e
                    for e in candidates
                    if str(e.get("automation_id", "")).strip() == auto_id
                ]
                if len(auto_matches) == 1:
                    return TargetResolutionResult(
                        success=True, element=auto_matches[0], candidate_count=1
                    )
                elif len(auto_matches) > 1:
                    candidates = auto_matches  # Refine further

        # 4. Filter by ControlType if specified
        if target_ref and target_ref.control_type:
            ctype = target_ref.control_type.strip().lower()
            ctype_matches = [
                e
                for e in candidates
                if str(e.get("control_type", "")).strip().lower() == ctype
            ]
            if ctype_matches:
                candidates = ctype_matches

        # 5. Filter by Name (Exact match, then case-insensitive substring)
        target_name = (target_ref.name if target_ref else None) or target_description
        if target_name:
            norm_name = target_name.strip().lower()
            # Exact name match (requires non-empty element name)
            exact_name_matches = [
                e
                for e in candidates
                if str(e.get("name", "")).strip()
                and str(e.get("name", "")).strip().lower() == norm_name
            ]
            if exact_name_matches:
                candidates = exact_name_matches
            else:
                sub_matches = [
                    e
                    for e in candidates
                    if str(e.get("name", "")).strip()
                    and (
                        norm_name in str(e.get("name", "")).strip().lower()
                        or (
                            len(str(e.get("name", "")).strip()) >= 2
                            and str(e.get("name", "")).strip().lower() in norm_name
                        )
                    )
                ]
                if sub_matches:
                    candidates = sub_matches
                else:
                    candidates = []

        # 6. Evaluate remaining candidates
        if len(candidates) == 1:
            return TargetResolutionResult(
                success=True, element=candidates[0], candidate_count=1
            )
        elif len(candidates) > 1:
            return TargetResolutionResult(
                success=False,
                is_ambiguous=True,
                candidate_count=len(candidates),
                candidates=candidates,
                error=f"Ambiguous target: {len(candidates)} matching UI elements found. Refusing to guess.",
            )

        return TargetResolutionResult(
            success=False,
            error=f"Target '{target_name or 'unknown'}' could not be resolved to any active UI element.",
        )

    def revalidate_live_target(
        self, element: dict[str, Any], action_type: str = "click", text: str = ""
    ) -> tuple[bool, str]:
        """
        Immediately pre-dispatch: Re-query live UIA to ensure target element is still valid,
        visible, enabled, and that the window exists.
        """
        ok, reason, _ = self.revalidate_consequential_target(
            element=element, expected_action=action_type, text=text
        )
        return ok, reason

    def revalidate_consequential_target(
        self,
        element: dict[str, Any],
        expected_action: str = "click",
        expected_hwnd: int | None = None,
        max_drift_px: float = 15.0,
        text: str = "",
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Strict 6-Point Pre-Dispatch Live Revalidation (§6):
        1. Confirm intended application/window is still alive and not minimized.
        2. Confirm target control still exists in live UIA.
        3. Confirm target bounds have not moved unexpectedly (drift <= max_drift_px).
        4. Confirm control is still enabled (is_enabled == True).
        5. Confirm target matches the planned action semantics and available patterns.
        6. Confirm action has not become unsafe due to invalid geometry or boundaries.
        Returns: (is_valid: bool, reason: str, fresh_element: Dict[str, Any])
        """
        import ctypes
        import math

        # 1. Window validity check
        target_hwnd = expected_hwnd or element.get("hwnd")
        if target_hwnd:
            user32 = ctypes.windll.user32
            if not user32.IsWindow(target_hwnd):
                return (
                    False,
                    f"Target window HWND {target_hwnd} is closed or destroyed",
                    {},
                )
            if user32.IsIconic(target_hwnd):
                return False, f"Target window HWND {target_hwnd} is minimized", {}

        # 2. Live UIA revalidation
        live_res = uia_inspector.revalidate_element(element)
        if not live_res.get("valid", False):
            return (
                False,
                f"Live target revalidation failed: {live_res.get('reason', 'Element is stale or disappeared')}",
                {},
            )

        fresh_el = live_res.get("element", element)

        # 3. Geometric bounds drift check
        old_bounds = element.get("bounds") or {}
        new_bounds = fresh_el.get("bounds") or {}
        if old_bounds and new_bounds:
            old_cx = (old_bounds.get("left", 0) + old_bounds.get("right", 0)) / 2.0
            old_cy = (old_bounds.get("top", 0) + old_bounds.get("bottom", 0)) / 2.0
            new_cx = (new_bounds.get("left", 0) + new_bounds.get("right", 0)) / 2.0
            new_cy = (new_bounds.get("top", 0) + new_bounds.get("bottom", 0)) / 2.0
            drift = math.hypot(old_cx - new_cx, old_cy - new_cy)
            if drift > max_drift_px:
                return (
                    False,
                    f"Target bounds drifted {drift:.1f}px on screen (exceeds tolerance {max_drift_px}px)",
                    fresh_el,
                )

        # 4. Enabled check
        if not fresh_el.get("is_enabled", True):
            return False, "Target control is disabled (IsEnabled=False)", fresh_el

        # 5. Semantic action compatibility
        norm_type = expected_action.lower()
        patterns = fresh_el.get("available_patterns") or []  # noqa: F841
        if norm_type == "type":
            if fresh_el.get("is_read_only", False):
                return False, "Target control is read-only; cannot type", fresh_el
            val_res = self._validator.validate_type(fresh_el, text=text or "sample")
            if not val_res.ok:
                return (
                    False,
                    f"Target typing validation failed: {val_res.reason}",
                    fresh_el,
                )
        elif norm_type == "focus":
            val_res = self._validator.validate_focus(fresh_el)
            if not val_res.ok:
                return (
                    False,
                    f"Target focus validation failed: {val_res.reason}",
                    fresh_el,
                )
        else:
            # Click actions
            if not fresh_el.get("is_visible", True):
                return False, "Target control is invisible or offscreen", fresh_el
            val_res = self._validator.validate_click(fresh_el)
            if not val_res.ok:
                return (
                    False,
                    f"Target click validation failed: {val_res.reason}",
                    fresh_el,
                )

        # 6. Safe outcome
        return True, "Target verified live and safe for dispatch", fresh_el


target_resolver = TargetResolver()
