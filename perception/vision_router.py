"""
COMPASS Phase 7 — Vision Model Routing & Fallback
Coordinates with Phase 5 OmniRoute / Model Router to query vision models when available,
or safely emit AI_UNAVAILABLE for deterministic UIA/OCR fallback (Section 18, 20).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from perception.models_multimodal import (
    BoundingBox,
    CapabilityStatus,
    CoordinateSpace,
    EvidenceProvenance,
    EvidenceSource,
    MultimodalEvidence,
)

logger = logging.getLogger(__name__)


class VisionRouter:
    """
    Interfaces between Multimodal Perception and OmniRoute (Phase 5).
    Provides safe, bounded vision model inference with deterministic fallbacks.
    """

    def __init__(self, omniroute_manager: Any | None = None):
        self._omniroute = omniroute_manager
        self._is_busy = False

    def is_vision_model_available(self) -> bool:
        """Check if a verified vision model is currently configured and reachable."""
        if not self._omniroute:
            return False
        try:
            # Check for vision-capable models in Phase 5 registry
            if hasattr(self._omniroute, "get_vision_model"):
                model = self._omniroute.get_vision_model()
                return model is not None
            return False
        except Exception:  # noqa: BLE001
            return False

    def get_capability_status(self) -> CapabilityStatus:
        if self.is_vision_model_available():
            return CapabilityStatus.AVAILABLE
        return CapabilityStatus.UNAVAILABLE

    def analyze_screenshot(
        self,
        image_path: str,
        query: str,
        timeout_sec: float = 10.0,
    ) -> tuple[CapabilityStatus, str | None, list[MultimodalEvidence]]:
        """
        Analyze screenshot using vision model if available.
        Returns (Status, TextualAnswer, EvidenceList).
        If model is unavailable, returns (CapabilityStatus.UNAVAILABLE, None, []).
        """
        if not self.is_vision_model_available():
            return CapabilityStatus.UNAVAILABLE, None, []

        if self._is_busy:
            logger.warning(
                "Vision model is busy; enforcing single active inference rule"
            )
            return CapabilityStatus.PARTIAL, "BUSY", []

        self._is_busy = True
        try:
            # Call vision model through OmniRoute
            # (Phase 5 OmniRoute call wrapper)
            t0 = time.time()  # noqa: F841
            res = self._omniroute.call_vision(
                image_path=image_path, prompt=query, timeout=timeout_sec
            )
            evidence: list[MultimodalEvidence] = []
            if res and isinstance(res, dict):
                answer = res.get("text", "")
                boxes = res.get("boxes", [])
                for b in boxes:
                    bbox = BoundingBox.from_ltwh(
                        b.get("x", 0),
                        b.get("y", 0),
                        b.get("w", 50),
                        b.get("h", 20),
                        CoordinateSpace.SCREEN_PHYSICAL,
                    )
                    evidence.append(
                        MultimodalEvidence(
                            source=EvidenceSource.VISUAL_MODEL,
                            bounding_box=bbox,
                            extracted_text=b.get("label", ""),
                            confidence=b.get("confidence", 0.8),
                            provenance=EvidenceProvenance(
                                source=EvidenceSource.VISUAL_MODEL,
                                source_version=res.get(
                                    "model_name", "omniroute_vision"
                                ),
                            ),
                            is_untrusted=True,
                        )
                    )
                return CapabilityStatus.AVAILABLE, answer, evidence
            return CapabilityStatus.UNAVAILABLE, None, []
        except Exception as e:  # noqa: BLE001
            logger.error("Vision model inference failed: %s", e)
            return CapabilityStatus.UNAVAILABLE, None, []
        finally:
            self._is_busy = False
