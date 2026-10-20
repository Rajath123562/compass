"""
COMPASS Phase 7 — Multimodal Perception Evidence Models
Canonical data models for UIA, Screen Capture, OCR, Visual Models, and Cross-Modal Evidence Fusion.

Fully preserves provenance, coordinate spaces, DPI context, and confidence ratings.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceSource(str, Enum):
    """Supported multimodal evidence sources (Section 7)."""

    UIA = "UIA"
    SCREEN_CAPTURE = "SCREEN_CAPTURE"
    OCR = "OCR"
    WINDOW_STATE = "WINDOW_STATE"
    VISUAL_MODEL = "VISUAL_MODEL"
    CURSOR = "CURSOR"
    APPLICATION_STATE = "APPLICATION_STATE"
    TEMPORAL_COMPARISON = "TEMPORAL_COMPARISON"


class CapabilityStatus(str, Enum):
    """Capability verification status (Section 6)."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    UNVERIFIED = "UNVERIFIED"


class ConsistencyOutcome(str, Enum):
    """Cross-modal consistency classification (Section 11)."""

    CONSISTENT = "CONSISTENT"
    UIA_ONLY = "UIA_ONLY"
    VISION_ONLY = "VISION_ONLY"
    OCR_ONLY = "OCR_ONLY"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class ResolutionMethod(str, Enum):
    """Target resolution strategy (Section 12)."""

    EXACT_UIA = "exact_uia"
    SEMANTIC_UIA = "semantic_uia"
    OCR_TEXT = "ocr_text"
    VISUAL_BBOX = "visual_bbox"
    RELATIVE_LAYOUT = "relative_layout"
    WINDOW_CONTEXT = "window_context"
    FUSED_MULTI = "fused_multi"


class CoordinateSpace(str, Enum):
    """Coordinate space definition for multi-monitor / DPI handling (Section 10)."""

    SCREEN_PHYSICAL = "screen_physical"  # GDI / native screen pixels
    SCREEN_LOGICAL_DPI = "screen_logical_dpi"  # DPI-scaled desktop coordinates
    WINDOW_RELATIVE = "window_relative"  # Relative to target window top-left
    NORMALIZED_01 = "normalized_01"  # Normalized [0.0, 1.0] within window/screen
    LOGICAL = "LOGICAL"
    PHYSICAL = "PHYSICAL"
    SCREEN_LOGICAL = "screen_logical"
    NORMALIZED = "normalized"


@dataclass
class BoundingBox:
    """
    Robust bounding box supporting coordinate spaces, multi-monitor negative coords,
    intersection-over-union (IoU), and containment tests.
    """

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    coordinate_space: CoordinateSpace = CoordinateSpace.SCREEN_PHYSICAL

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0

    def contains_point(self, x: int, y: int) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def intersects(self, other: BoundingBox) -> bool:
        if not self.is_valid or not other.is_valid:
            return False
        return not (
            self.right <= other.left
            or self.left >= other.right
            or self.bottom <= other.top
            or self.top >= other.bottom
        )

    def iou(self, other: BoundingBox) -> float:
        """Calculate Intersection over Union (IoU) between two bounding boxes."""
        if not self.is_valid or not other.is_valid:
            return 0.0

        inter_left = max(self.left, other.left)
        inter_top = max(self.top, other.top)
        inter_right = min(self.right, other.right)
        inter_bottom = min(self.bottom, other.bottom)

        inter_w = max(0, inter_right - inter_left)
        inter_h = max(0, inter_bottom - inter_top)
        inter_area = inter_w * inter_h

        if inter_area == 0:
            return 0.0

        union_area = self.area + other.area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
            "coordinate_space": self.coordinate_space.value
            if isinstance(self.coordinate_space, CoordinateSpace)
            else str(self.coordinate_space),
        }

    @classmethod
    def from_ltwh(
        cls,
        left: int,
        top: int,
        width: int,
        height: int,
        coordinate_space: CoordinateSpace = CoordinateSpace.SCREEN_PHYSICAL,
    ) -> BoundingBox:
        return cls(
            left=left,
            top=top,
            right=left + width,
            bottom=top + height,
            coordinate_space=coordinate_space,
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BoundingBox:
        coord_space = d.get("coordinate_space", CoordinateSpace.SCREEN_PHYSICAL.value)
        try:
            space_enum = CoordinateSpace(coord_space)
        except ValueError:
            space_enum = CoordinateSpace.SCREEN_PHYSICAL
        return cls(
            left=d.get("left", 0),
            top=d.get("top", 0),
            right=d.get("right", d.get("left", 0) + d.get("width", 0)),
            bottom=d.get("bottom", d.get("top", 0) + d.get("height", 0)),
            coordinate_space=space_enum,
        )


@dataclass
class EvidenceProvenance:
    """Provenance tracking for perception evidence (Section 7)."""

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: EvidenceSource = EvidenceSource.UIA
    source_version: str = "1.0.0"
    timestamp: float = field(default_factory=time.time)
    validity_duration_seconds: float = 10.0  # Validity window before staleness
    capture_hash: str | None = None  # Hash of screenshot/data if applicable
    device_context: dict[str, Any] = field(default_factory=dict)  # Monitor, DPI, etc.

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.validity_duration_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source.value
            if isinstance(self.source, EvidenceSource)
            else str(self.source),
            "source_version": self.source_version,
            "timestamp": self.timestamp,
            "validity_duration_seconds": self.validity_duration_seconds,
            "capture_hash": self.capture_hash,
            "device_context": dict(self.device_context),
            "is_expired": self.is_expired,
        }


@dataclass
class MultimodalEvidence:
    """
    Canonical evidence item produced by any perception modality (Section 7).
    Never merge evidence without preserving this canonical format.
    """

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    observation_id: str = ""
    task_id: str = ""
    step_id: str = ""
    source: EvidenceSource = EvidenceSource.UIA
    application: str = ""
    window_title: str = ""
    hwnd: int = 0
    bounding_box: BoundingBox = field(default_factory=BoundingBox)
    extracted_text: str = ""
    confidence: float = (
        1.0  # 1.0 for deterministic UIA; 0.0-1.0 for probabilistic OCR/vision
    )
    provenance: EvidenceProvenance = field(default_factory=EvidenceProvenance)
    uia_reference: dict[str, Any] | None = (
        None  # AutomationId, RuntimeId, ControlType
    )
    correlation_ids: list[str] = field(default_factory=list)  # Linked evidence IDs
    metadata: dict[str, Any] = field(default_factory=dict)
    is_untrusted: bool = True  # Screen & OCR text is untrusted by default (Section 17)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "observation_id": self.observation_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "source": self.source.value
            if isinstance(self.source, EvidenceSource)
            else str(self.source),
            "application": self.application,
            "window_title": self.window_title,
            "hwnd": self.hwnd,
            "bounding_box": self.bounding_box.to_dict(),
            "extracted_text": self.extracted_text,
            "confidence": self.confidence,
            "provenance": self.provenance.to_dict(),
            "uia_reference": self.uia_reference,
            "correlation_ids": list(self.correlation_ids),
            "metadata": dict(self.metadata),
            "is_untrusted": self.is_untrusted,
        }


@dataclass
class ObservationSnapshot:
    """
    Complete multimodal snapshot capturing current Windows state at a point in time (Section 7, 13).
    """

    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    task_id: str = ""
    step_id: str = ""
    monitor_id: int = 0
    dpi_scaling: float = 1.0
    screenshot_path: str | None = None
    screenshot_hash: str | None = None
    window_hwnd: int = 0
    window_title: str = ""
    window_bounds: BoundingBox = field(default_factory=BoundingBox)
    evidence_items: list[MultimodalEvidence] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_by_source(self, source: EvidenceSource) -> list[MultimodalEvidence]:
        return [e for e in self.evidence_items if e.source == source]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "monitor_id": self.monitor_id,
            "dpi_scaling": self.dpi_scaling,
            "screenshot_path": self.screenshot_path,
            "screenshot_hash": self.screenshot_hash,
            "window_hwnd": self.window_hwnd,
            "window_title": self.window_title,
            "window_bounds": self.window_bounds.to_dict(),
            "evidence_count": len(self.evidence_items),
            "evidence_items": [e.to_dict() for e in self.evidence_items],
            "metadata": dict(self.metadata),
        }


@dataclass
class ResolvedTarget:
    """
    Output of Cross-Modal Target Resolution (Section 12).
    Ready for safety validation and execution dispatch.
    """

    target_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    bounding_box: BoundingBox = field(default_factory=BoundingBox)
    center_point: tuple[int, int] = (0, 0)
    confidence: float = 0.0
    resolution_method: ResolutionMethod = ResolutionMethod.FUSED_MULTI
    evidence_ids: list[str] = field(default_factory=list)
    consistency: ConsistencyOutcome = ConsistencyOutcome.CONSISTENT
    application: str = ""
    window_title: str = ""
    hwnd: int = 0
    is_stale: bool = False
    observation_id: str = ""
    task_id: str = ""
    step_id: str = ""
    monitor_id: int = 0
    monitor_topology_fingerprint: str = ""
    dpi_context: float = 1.0
    coordinate_space: CoordinateSpace = CoordinateSpace.SCREEN_PHYSICAL
    target_state: str = "active"
    evidence_fingerprint: str = ""
    created_at: float = field(default_factory=time.time)
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.bounding_box.is_valid and self.center_point == (0, 0):
            self.center_point = self.bounding_box.center

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "name": self.name,
            "bounding_box": self.bounding_box.to_dict(),
            "center_point": self.center_point,
            "confidence": self.confidence,
            "resolution_method": self.resolution_method.value
            if isinstance(self.resolution_method, ResolutionMethod)
            else str(self.resolution_method),
            "evidence_ids": list(self.evidence_ids),
            "consistency": self.consistency.value
            if isinstance(self.consistency, ConsistencyOutcome)
            else str(self.consistency),
            "application": self.application,
            "window_title": self.window_title,
            "hwnd": self.hwnd,
            "is_stale": self.is_stale,
            "observation_id": self.observation_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "monitor_id": self.monitor_id,
            "monitor_topology_fingerprint": self.monitor_topology_fingerprint,
            "dpi_context": self.dpi_context,
            "coordinate_space": self.coordinate_space.value
            if isinstance(self.coordinate_space, CoordinateSpace)
            else str(self.coordinate_space),
            "target_state": self.target_state,
            "evidence_fingerprint": self.evidence_fingerprint,
            "created_at": self.created_at,
            "reasons": list(self.reasons),
        }


@dataclass
class MultimodalVerificationResult:
    """Result of multimodal step or goal verification (Section 22)."""

    verified: bool = False
    confidence: float = 0.0
    verification_method: str = "multimodal_fusion"
    evidence_used: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    discrepancies: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "confidence": self.confidence,
            "verification_method": self.verification_method,
            "evidence_used": list(self.evidence_used),
            "details": dict(self.details),
            "discrepancies": list(self.discrepancies),
            "timestamp": self.timestamp,
        }


# Section 6 Taxonomy Dictionary
CAPABILITY_TAXONOMY_DEFAULT = {
    "screenshot_capture": CapabilityStatus.AVAILABLE,
    "screen_region_capture": CapabilityStatus.AVAILABLE,
    "window_capture": CapabilityStatus.AVAILABLE,
    "ui_tree_capture": CapabilityStatus.AVAILABLE,
    "OCR": CapabilityStatus.AVAILABLE,
    "text_region_detection": CapabilityStatus.AVAILABLE,
    "visual_element_detection": CapabilityStatus.PARTIAL,
    "icon_detection": CapabilityStatus.PARTIAL,
    "button_detection": CapabilityStatus.AVAILABLE,
    "field_detection": CapabilityStatus.AVAILABLE,
    "menu_detection": CapabilityStatus.AVAILABLE,
    "dialog_detection": CapabilityStatus.AVAILABLE,
    "visual_target_grounding": CapabilityStatus.AVAILABLE,
    "UIA_target_grounding": CapabilityStatus.AVAILABLE,
    "multimodal_target_grounding": CapabilityStatus.AVAILABLE,
    "image_understanding": CapabilityStatus.PARTIAL,
    "screenshot_understanding": CapabilityStatus.AVAILABLE,
    "document_image_understanding": CapabilityStatus.PARTIAL,
    "layout_understanding": CapabilityStatus.AVAILABLE,
    "cross_modal_alignment": CapabilityStatus.AVAILABLE,
    "evidence_fusion": CapabilityStatus.AVAILABLE,
    "temporal_state_comparison": CapabilityStatus.AVAILABLE,
    "visual_change_detection": CapabilityStatus.AVAILABLE,
    "OCR_text_matching": CapabilityStatus.AVAILABLE,
    "coordinate_grounding": CapabilityStatus.AVAILABLE,
}

# Re-export Phase 2 models without clobbering Phase 7 multimodal definitions
_mm_multimodal_evidence = MultimodalEvidence
_mm_coordinate_space = CoordinateSpace
from perception.models import *  # noqa: F401, F403
MultimodalEvidence = _mm_multimodal_evidence
CoordinateSpace = _mm_coordinate_space
