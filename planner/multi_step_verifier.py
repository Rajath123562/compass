"""
COMPASS Phase 6 — Multi-Step & Goal Verifier
Dual-layer verification engine evaluating both:
1. Step-level verification (action-specific state deltas on target controls).
2. Goal-level verification (global task objective realization, file creation, terminal UI states).
Prevents false-success where individual actions succeed but the overarching goal remains unachieved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.models import (
    DecomposedPlan,
    EvidenceSource,
    TaskStep,
    VerificationResult,
    VerificationStatus,
)
from planner.verification_engine import VerificationEngine


class MultiStepVerifier:
    """
    Evaluates step-level and goal-level verification conditions with evidence capture.
    """

    def __init__(self, base_verifier: VerificationEngine | None = None):
        self.base_verifier = base_verifier or VerificationEngine()

    def verify_step(
        self,
        step: TaskStep,
        pre_state: dict[str, Any] | None,
        post_state: dict[str, Any] | None,
        action_type: str,
    ) -> VerificationResult:
        """
        Verify individual step execution using its configured verification_strategy.
        """
        strat = step.verification_strategy.upper()
        cond = step.completion_condition or {}

        # 1. Window State Verification
        if strat == "WINDOW_STATE" or "window_title_contains" in cond:
            expected_title = cond.get("window_title_contains") or ""
            actual_title = (post_state or {}).get("window", {}).get("title", "")
            if expected_title.lower() in actual_title.lower():
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Window title '{actual_title}' matches expected substring '{expected_title}'.",
                    observed_state={"title": actual_title},
                    expected_state={"window_title_contains": expected_title},
                    evidence={"window": post_state.get("window") if post_state else {}},
                    evidence_source=EvidenceSource.WINDOW_STATE,
                )
            if not actual_title:
                # Check top-level visible windows in case focus was still on terminal or shifted
                import ctypes

                u32 = ctypes.windll.user32
                found_title = None

                def _enum_w(h, l):
                    nonlocal found_title
                    if u32.IsWindowVisible(h):
                        length = u32.GetWindowTextLengthW(h)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            u32.GetWindowTextW(h, buf, length + 1)
                            if expected_title.lower() in buf.value.lower():
                                found_title = buf.value
                                try:
                                    u32.SetForegroundWindow(h)
                                except Exception:  # noqa: BLE001, S110
                                    pass
                                return False
                    return True

                try:
                    WNDENUM = ctypes.WINFUNCTYPE(
                        ctypes.c_bool, ctypes.c_int, ctypes.c_int
                    )
                    u32.EnumWindows(WNDENUM(_enum_w), 0)
                except Exception:  # noqa: BLE001, S110
                    pass

                if found_title:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Window title '{found_title}' found in visible windows matching expected substring '{expected_title}'.",
                        observed_state={"title": found_title},
                        expected_state={"window_title_contains": expected_title},
                        evidence={"window": {"title": found_title}},
                        evidence_source=EvidenceSource.WINDOW_STATE,
                    )

            return VerificationResult(
                status=VerificationStatus.FAILED,
                details=f"Expected window title containing '{expected_title}', but found '{actual_title}'.",
                observed_state={"title": actual_title},
                expected_state={"window_title_contains": expected_title},
                evidence_source=EvidenceSource.WINDOW_STATE,
            )

        # 2. Filesystem Verification
        elif strat == "FILESYSTEM" or "file_path" in cond:
            filepath = cond.get("file_path")
            if filepath and Path(filepath).exists():
                size = Path(filepath).stat().st_size
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"File '{filepath}' exists on filesystem ({size} bytes).",
                    observed_state={"exists": True, "size": size},
                    expected_state={"file_path": filepath},
                    evidence={"filepath": filepath, "size": size},
                    evidence_source=EvidenceSource.FILESYSTEM,
                )
            else:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    details=f"File '{filepath}' does not exist on filesystem.",
                    observed_state={"exists": False},
                    expected_state={"file_path": filepath},
                    evidence_source=EvidenceSource.FILESYSTEM,
                )

        # 3. UIA Pattern / Control State Verification
        elif strat == "UIA_PATTERN":
            text_expected = cond.get("text_contains")
            if text_expected:
                # Inspect post-state editor text
                edit_text = (
                    (post_state or {}).get("edit_text")
                    or (post_state or {}).get("element_value")
                    or ""
                )
                if text_expected in edit_text:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Target control contains expected text: '{text_expected}'.",
                        observed_state={"text": edit_text},
                        expected_state={"text_contains": text_expected},
                        evidence_source=EvidenceSource.UIA,
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.UNVERIFIED,
                        details=f"Target control text '{edit_text}' does not contain expected '{text_expected}'.",
                        observed_state={"text": edit_text},
                        expected_state={"text_contains": text_expected},
                        evidence_source=EvidenceSource.UIA,
                    )

        # 4. Multimodal / Vision / OCR Verification (Phase 7)
        elif (
            strat == "MULTIMODAL"
            or "ocr_text_contains" in cond
            or "visual_delta" in cond
        ):
            ocr_expected = cond.get("ocr_text_contains") or cond.get("expected_text")
            ocr_text = (post_state or {}).get("ocr_text") or ""
            pixel_diff = (post_state or {}).get("pixel_difference_ratio", 0.0)

            if ocr_expected:
                if ocr_expected.lower() in ocr_text.lower():
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Multimodal OCR verified presence of text '{ocr_expected}'.",
                        observed_state={"ocr_text": ocr_text},
                        expected_state={"ocr_text_contains": ocr_expected},
                        evidence_source=EvidenceSource.OCR,
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.UNVERIFIED,
                        details=f"Multimodal OCR did not detect expected text '{ocr_expected}'. Observed: '{ocr_text[:100]}'.",
                        observed_state={"ocr_text": ocr_text},
                        expected_state={"ocr_text_contains": ocr_expected},
                        evidence_source=EvidenceSource.OCR,
                    )
            elif "visual_delta" in cond:
                min_diff = cond.get("visual_delta", 0.01)
                if pixel_diff >= min_diff:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Multimodal visual change confirmed (delta: {pixel_diff:.4f} >= {min_diff}).",
                        observed_state={"pixel_diff": pixel_diff},
                        expected_state={"min_diff": min_diff},
                        evidence_source=EvidenceSource.SCREEN_CAPTURE,
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.UNVERIFIED,
                        details=f"Multimodal visual change below threshold (delta: {pixel_diff:.4f} < {min_diff}).",
                        observed_state={"pixel_diff": pixel_diff},
                        expected_state={"min_diff": min_diff},
                        evidence_source=EvidenceSource.SCREEN_CAPTURE,
                    )

        # Fallback to Phase 5 base verification engine
        return self.base_verifier.verify_action(
            action_type=action_type,
            target_description=step.target_description,
            pre_obs=pre_state,
            post_obs=post_state,
        )

    def verify_final_goal(
        self,
        plan: DecomposedPlan,
        live_window: dict[str, Any] | None,
        filesystem_checks: list[str] | None = None,
    ) -> VerificationResult:
        """
        Verify that the entire user goal has genuinely succeeded.
        Ensures all individual steps are verified AND final system state confirms completion.
        """
        # 1. Check step completion status
        uncompleted = [s for s in plan.steps if s.status != "COMPLETED"]
        if uncompleted:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                details=f"Goal cannot be verified: {len(uncompleted)} steps remain uncompleted ({[s.step_id for s in uncompleted]}).",
                evidence_source=EvidenceSource.UIA,
            )

        # 2. Check filesystem side effects if requested
        if filesystem_checks:
            for fpath in filesystem_checks:
                if not Path(fpath).exists():
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        details=f"Goal verification failed: Expected file '{fpath}' does not exist on disk.",
                        evidence_source=EvidenceSource.FILESYSTEM,
                    )

        # 3. All checks verified
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            details=f"Final goal verification confirmed for task [{plan.task_id}]: All {len(plan.steps)} steps verified.",
            observed_state={"completed_steps_count": len(plan.steps)},
            expected_state={"all_steps_completed": True},
            evidence={"task_id": plan.task_id, "goal": plan.goal},
            evidence_source=EvidenceSource.WINDOW_STATE,
        )
