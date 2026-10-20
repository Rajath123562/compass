"""
COMPASS Phase 4 — Evidence-Based Confidence Engine
Evaluates decision certainty using multi-signal evidence fusion.
Degrades confidence when evidence signals conflict; never relies on fake 1.0 certainty.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.app.logging_config import logger
from planner.models import ConfidenceLevel, TargetReference


class ConfidenceEvaluation(BaseModel):
    level: ConfidenceLevel
    score: float
    signals: dict[str, Any]
    conflict_detected: bool = False
    conflict_details: str | None = None


class ConfidenceEngine:
    """
    Multi-signal evidence evaluator for targets and planned actions.
    Considers UIA identification, active window context, enabled/visibility state,
    bounding rect validity, observation freshness, past verification history,
    and visual/OCR consistency.
    """

    def __init__(self):
        pass

    def evaluate_confidence(
        self,
        target_ref: TargetReference | None,
        element_snapshot: dict[str, Any] | None,
        active_window: dict[str, Any] | None = None,
        observation_age_ms: float = 0.0,
        visual_evidence: dict[str, Any] | None = None,
        past_verification_ok: bool | None = None,
    ) -> ConfidenceEvaluation:
        """
        Evaluate composite confidence across all evidence signals.
        """
        signals: dict[str, Any] = {}
        conflict_detected = False
        conflict_details = None

        # 1. Target existence check
        if not element_snapshot:
            # If target_ref is None, this is a target-free action (launch_app, open_url, wait, etc.)
            if target_ref is None:
                signals["target_existence"] = 1.0
                signals["target_free_action"] = 1.0
                return ConfidenceEvaluation(
                    level=ConfidenceLevel.HIGH,
                    score=0.95,
                    signals=signals,
                    conflict_detected=False,
                )
            signals["target_existence"] = 0.0
            return ConfidenceEvaluation(
                level=ConfidenceLevel.UNKNOWN,
                score=0.0,
                signals=signals,
                conflict_detected=True,
                conflict_details="Target element not found in current UI observation",
            )

        signals["target_existence"] = 1.0

        # 2. Identification match strength signal
        # Use evidence weights, never fake 100% certainty
        match_score = 0.50
        match_type = "unknown"

        if target_ref:
            ref_rt = target_ref.runtime_id
            snap_rt = element_snapshot.get("runtime_id")
            ref_aid = target_ref.automation_id
            snap_aid = element_snapshot.get("automation_id")
            ref_name = target_ref.name
            snap_name = element_snapshot.get("name")

            if ref_rt and snap_rt and ref_rt == snap_rt:
                match_score = 0.90  # Evidence signal, not absolute 1.0
                match_type = "runtime_id"
            elif ref_aid and snap_aid and ref_aid == snap_aid:
                match_score = 0.85
                match_type = "automation_id"
            elif ref_name and snap_name and ref_name.lower() == snap_name.lower():
                match_score = 0.80
                match_type = "exact_name"
            elif (
                ref_name
                and snap_name
                and (
                    ref_name.lower() in snap_name.lower()
                    or snap_name.lower() in ref_name.lower()
                )
            ):
                match_score = 0.65
                match_type = "substring_name"
            else:
                match_score = 0.40
                match_type = "weak_match"

        signals["match_type"] = match_type
        signals["match_score"] = match_score

        score = match_score

        # 3. Enabled and actionable state
        is_enabled = element_snapshot.get("is_enabled", True)
        signals["is_enabled"] = is_enabled
        if not is_enabled:
            score -= 0.35
            signals["disabled_penalty"] = -0.35

        # 4. Bounding rectangle plausibility
        bounds = element_snapshot.get("bounding_rect") or element_snapshot.get("bounds")
        valid_bounds = False
        if bounds and isinstance(bounds, dict):
            w = bounds.get("width", 0)
            h = bounds.get("height", 0)
            area = w * h
            if area > 0:
                valid_bounds = True
        signals["valid_bounds"] = valid_bounds
        if not valid_bounds:
            score -= 0.30
            signals["invalid_bounds_penalty"] = -0.30

        # 5. Active window context match
        if active_window:
            target_hwnd = element_snapshot.get("hwnd") or (
                target_ref.hwnd if target_ref else None
            )
            active_hwnd = active_window.get("hwnd")
            if target_hwnd and active_hwnd:
                if target_hwnd == active_hwnd:
                    score += 0.05
                    signals["active_window_match"] = True
                else:
                    score -= 0.25
                    signals["active_window_match"] = False
                    signals["background_window_penalty"] = -0.25

        # 6. Observation freshness
        signals["observation_age_ms"] = observation_age_ms
        if observation_age_ms > 10000:
            score -= 0.40
            signals["age_penalty"] = -0.40
        elif observation_age_ms > 5000:
            score -= 0.20
            signals["age_penalty"] = -0.20

        # 7. Conflicting evidence check (e.g. UIA vs Vision/OCR)
        if visual_evidence:
            vision_label = str(visual_evidence.get("text", "")).strip().lower()
            uia_name = str(element_snapshot.get("name", "")).strip().lower()
            if vision_label and uia_name:  # noqa: SIM102
                if vision_label not in uia_name and uia_name not in vision_label:
                    conflict_detected = True
                    conflict_details = f"Visual/OCR text '{vision_label}' conflicts with UIA name '{uia_name}'"
                    score -= 0.45
                    signals["conflict_penalty"] = -0.45
                    signals["conflict_details"] = conflict_details
                    logger.warning(
                        f"ConfidenceEngine: Contradictory evidence detected: {conflict_details}"
                    )

        # 8. Past verification history
        if past_verification_ok is True:
            score += 0.05
            signals["past_verification_bonus"] = 0.05
        elif past_verification_ok is False:
            score -= 0.20
            signals["past_verification_failure_penalty"] = -0.20

        # Final score clamping and confidence level derivation
        final_score = max(0.0, min(0.98, score))

        # In case of severe conflict, confidence cannot exceed LOW
        if conflict_detected and final_score >= 0.5:
            final_score = 0.45

        level = ConfidenceLevel.from_score(final_score)
        if final_score < 0.2:
            level = ConfidenceLevel.UNKNOWN

        return ConfidenceEvaluation(
            level=level,
            score=round(final_score, 3),
            signals=signals,
            conflict_detected=conflict_detected,
            conflict_details=conflict_details,
        )


confidence_engine = ConfidenceEngine()
