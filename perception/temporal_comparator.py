"""
COMPASS Phase 7 — Temporal Perception & Observation Comparator
Compares observations across time steps to detect UI changes, target movements,
unexpected dialogs, and verification state transitions (Section 13).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from perception.models_multimodal import (
    MultimodalEvidence,
    ObservationSnapshot,
)


class StateTransitionType(str, Enum):
    """Temporal state change classifications (Section 13)."""

    NO_CHANGE = "no_change"
    SIGNIFICANT_SCREEN_CHANGE = "significant_screen_change"
    TARGET_APPEARED = "target_appeared"
    TARGET_DISAPPEARED = "target_disappeared"
    TARGET_MOVED = "target_moved"
    TEXT_CHANGED = "text_changed"
    WINDOW_CHANGED = "window_changed"
    DIALOG_APPEARED = "dialog_appeared"
    APPLICATION_CHANGED = "application_changed"
    STATE_CHANGE_CONFIRMED = "state_change_confirmed"


@dataclass
class TemporalComparisonResult:
    """Detailed result of comparing two ObservationSnapshots."""

    comparison_id: str
    from_observation_id: str
    to_observation_id: str
    elapsed_seconds: float
    pixel_difference_ratio: float = 0.0  # 0.0 (identical) to 1.0 (completely different)
    detected_transitions: list[StateTransitionType] = field(default_factory=list)
    window_changed: bool = False
    app_changed: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def has_transition(self, trans: StateTransitionType) -> bool:
        return trans in self.detected_transitions

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "from_observation_id": self.from_observation_id,
            "to_observation_id": self.to_observation_id,
            "elapsed_seconds": self.elapsed_seconds,
            "pixel_difference_ratio": self.pixel_difference_ratio,
            "detected_transitions": [t.value for t in self.detected_transitions],
            "window_changed": self.window_changed,
            "app_changed": self.app_changed,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }


class TemporalComparator:
    """
    Compares two observations to provide temporal perception evidence.
    """

    def __init__(
        self, pixel_diff_threshold: float = 0.02, move_distance_threshold: int = 15
    ):
        self.pixel_diff_threshold = pixel_diff_threshold
        self.move_distance_threshold = move_distance_threshold

    def calculate_image_difference(
        self, img_path_a: str | None, img_path_b: str | None
    ) -> float:
        """
        Calculate the normalized pixel difference ratio between two images using Pillow.
        Returns float between 0.0 (identical) and 1.0 (completely different).
        """
        if not img_path_a or not img_path_b:
            return 0.0

        p_a = Path(img_path_a)
        p_b = Path(img_path_b)
        if not p_a.exists() or not p_b.exists():
            return 0.0

        try:
            from PIL import Image, ImageChops, ImageStat

            img_a = Image.open(p_a).convert("RGB")
            img_b = Image.open(p_b).convert("RGB")

            # Resize if dimensions differ
            if img_a.size != img_b.size:
                img_b = img_b.resize(img_a.size)

            diff = ImageChops.difference(img_a, img_b)
            # Downsample diff to 64x64 for fast and robust comparison
            diff_small = diff.resize((64, 64))
            stat = ImageStat.Stat(diff_small)
            # Calculate normalized average difference across RGB channels
            total_diff = sum(stat.mean) / (3.0 * 255.0)
            return min(1.0, max(0.0, total_diff))
        except Exception:  # noqa: BLE001
            return 0.0

    def compare_observations(
        self,
        obs_before: ObservationSnapshot,
        obs_after: ObservationSnapshot,
        expected_target_name: str | None = None,
    ) -> TemporalComparisonResult:
        """
        Compare obs_before and obs_after to detect state transitions.
        """
        transitions: list[StateTransitionType] = []
        details: dict[str, Any] = {}

        elapsed = max(0.0, obs_after.timestamp - obs_before.timestamp)

        # 1. Window & Application changes
        app_changed = False
        if obs_before.window_title and obs_after.window_title:  # noqa: SIM102
            if obs_before.window_title != obs_after.window_title:
                transitions.append(StateTransitionType.WINDOW_CHANGED)
                details["window_before"] = obs_before.window_title
                details["window_after"] = obs_after.window_title

        if (
            obs_before.window_hwnd != obs_after.window_hwnd
            and obs_before.window_hwnd > 0
            and obs_after.window_hwnd > 0
        ):
            transitions.append(StateTransitionType.APPLICATION_CHANGED)
            app_changed = True

        # 2. Pixel difference between screenshots
        diff_ratio = 0.0
        if obs_before.screenshot_path and obs_after.screenshot_path:
            diff_ratio = self.calculate_image_difference(
                obs_before.screenshot_path, obs_after.screenshot_path
            )
            details["pixel_diff_ratio"] = diff_ratio
            if diff_ratio > self.pixel_diff_threshold:
                transitions.append(StateTransitionType.SIGNIFICANT_SCREEN_CHANGE)

        # 3. Dialog appearance check
        dialog_after = any(
            "dialog" in e.extracted_text.lower()
            or (e.uia_reference and e.uia_reference.get("control_type") == "Window")
            for e in obs_after.evidence_items
        )
        dialog_before = any(
            "dialog" in e.extracted_text.lower()
            or (e.uia_reference and e.uia_reference.get("control_type") == "Window")
            for e in obs_before.evidence_items
        )
        if dialog_after and not dialog_before:
            transitions.append(StateTransitionType.DIALOG_APPEARED)

        # 4. Target movement or appearance/disappearance
        if expected_target_name:
            target_norm = expected_target_name.strip().lower()

            def _find_target(obs: ObservationSnapshot) -> MultimodalEvidence | None:
                for ev in obs.evidence_items:
                    if target_norm in ev.extracted_text.lower():
                        return ev
                return None

            t_before = _find_target(obs_before)
            t_after = _find_target(obs_after)

            if t_before and not t_after:
                transitions.append(StateTransitionType.TARGET_DISAPPEARED)
                details["target_disappeared"] = expected_target_name
            elif not t_before and t_after:
                transitions.append(StateTransitionType.TARGET_APPEARED)
                details["target_appeared"] = expected_target_name
            elif t_before and t_after:
                c1 = t_before.bounding_box.center
                c2 = t_after.bounding_box.center
                dist = math.hypot(c2[0] - c1[0], c2[1] - c1[1])
                if dist > self.move_distance_threshold:
                    transitions.append(StateTransitionType.TARGET_MOVED)
                    details["target_moved_distance"] = dist

        # 5. Text content changes
        texts_before = set(  # noqa: C401
            e.extracted_text.strip()
            for e in obs_before.evidence_items
            if len(e.extracted_text.strip()) > 3
        )
        texts_after = set(  # noqa: C401
            e.extracted_text.strip()
            for e in obs_after.evidence_items
            if len(e.extracted_text.strip()) > 3
        )
        if texts_before and texts_after and texts_before != texts_after:
            added = texts_after - texts_before
            removed = texts_before - texts_after
            if added or removed:
                transitions.append(StateTransitionType.TEXT_CHANGED)
                details["texts_added"] = list(added)[:5]
                details["texts_removed"] = list(removed)[:5]

        if not transitions:
            transitions.append(StateTransitionType.NO_CHANGE)

        comp_id = f"comp_{obs_before.observation_id[:8]}_{obs_after.observation_id[:8]}"
        return TemporalComparisonResult(
            comparison_id=comp_id,
            from_observation_id=obs_before.observation_id,
            to_observation_id=obs_after.observation_id,
            elapsed_seconds=round(elapsed, 3),
            pixel_difference_ratio=round(diff_ratio, 4),
            detected_transitions=transitions,
            window_changed=obs_before.window_title != obs_after.window_title,
            app_changed=app_changed,
            details=details,
        )


def calculate_image_diff_ratio(img1: Any, img2: Any) -> float:
    """Calculates the percentage of pixels that have changed between two images."""
    try:
        from PIL import ImageChops, ImageStat
    except ImportError:
        return 0.0

    if getattr(img1, "size", None) != getattr(img2, "size", None):
        return 1.0

    diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB"))
    stat = ImageStat.Stat(diff)
    overall_mean = sum(stat.mean) / len(stat.mean)
    return overall_mean / 255.0


def detect_transition_type(diff_ratio: float, threshold: float = 0.05) -> str:
    """Classifies the transition based on the diff ratio."""
    if diff_ratio > threshold:
        return "SIGNIFICANT_SCREEN_CHANGE"
    elif diff_ratio > 0.001:
        return "MINOR_SCREEN_CHANGE"
    else:
        return "UNCHANGED"
