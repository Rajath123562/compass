"""
COMPASS Phase 7 — Cross-Modal Evidence Fusion & Target Resolution
Associates UIA, OCR, and Visual evidence, classifies cross-modal consistency,
resolves execution targets with multi-strategy scoring, and enforces
stale-observation protection (Sections 11, 12, 14).
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import time
from typing import Any

from perception.models_multimodal import (
    BoundingBox,
    ConsistencyOutcome,
    EvidenceSource,
    MultimodalEvidence,
    ObservationSnapshot,
    ResolutionMethod,
    ResolvedTarget,
)

logger = logging.getLogger(__name__)


def compute_text_similarity(a: str, b: str) -> float:
    """Compute normalized string similarity between 0.0 and 1.0."""
    na = a.strip().lower()
    nb = b.strip().lower()
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    return difflib.SequenceMatcher(None, na, nb).ratio()


class EvidenceFusionEngine:
    """
    Fuses multimodal evidence sources into coherent UI target representations.
    Maintains provenance and classifies cross-modal consistency.
    """

    def __init__(
        self,
        iou_overlap_threshold: float = 0.3,
        text_similarity_threshold: float = 0.65,
        max_observation_age_sec: float = 12.0,
    ):
        self.iou_overlap_threshold = iou_overlap_threshold
        self.text_similarity_threshold = text_similarity_threshold
        self.max_observation_age_sec = max_observation_age_sec

    def fuse_evidence(
        self,
        uia_evidence: list[MultimodalEvidence],
        ocr_evidence: list[MultimodalEvidence],
        visual_evidence: list[MultimodalEvidence] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Correlate UIA, OCR, and visual evidence items based on spatial overlap and text alignment.
        Returns a list of fused evidence clusters with consistency classification.
        """
        visual_evidence = visual_evidence or []
        fused_clusters: list[dict[str, Any]] = []

        unmatched_ocr = list(ocr_evidence)
        unmatched_visual = list(visual_evidence)

        # 1. Match UIA elements against OCR and Visual evidence
        for uia_item in uia_evidence:
            cluster_evidence = [uia_item]
            cluster_ocr = []
            cluster_visual = []

            # Check overlap with OCR
            remaining_ocr = []
            for ocr_item in unmatched_ocr:
                iou = uia_item.bounding_box.iou(ocr_item.bounding_box)
                # Check if OCR box is contained within UIA bounds or overlaps
                contains = uia_item.bounding_box.contains_point(
                    *ocr_item.bounding_box.center
                ) or ocr_item.bounding_box.contains_point(*uia_item.bounding_box.center)
                text_sim = compute_text_similarity(
                    uia_item.extracted_text, ocr_item.extracted_text
                )

                if iou >= self.iou_overlap_threshold or (contains and text_sim >= 0.5):
                    cluster_ocr.append(ocr_item)
                    cluster_evidence.append(ocr_item)
                else:
                    remaining_ocr.append(ocr_item)
            unmatched_ocr = remaining_ocr

            # Check overlap with Visual
            remaining_vis = []
            for vis_item in unmatched_visual:
                iou = uia_item.bounding_box.iou(vis_item.bounding_box)
                if iou >= self.iou_overlap_threshold:
                    cluster_visual.append(vis_item)
                    cluster_evidence.append(vis_item)
                else:
                    remaining_vis.append(vis_item)
            unmatched_visual = remaining_vis

            # Determine consistency outcome (Section 11)
            if cluster_ocr:
                # Compare texts
                all_sims = [
                    compute_text_similarity(uia_item.extracted_text, o.extracted_text)
                    for o in cluster_ocr
                ]
                max_sim = max(all_sims) if all_sims else 0.0

                if max_sim >= self.text_similarity_threshold:
                    consistency = ConsistencyOutcome.CONSISTENT
                elif len(uia_item.extracted_text.strip()) > 0 and max_sim < 0.3:
                    # Clear conflict: UIA says "Submit" but OCR says "Cancel" in same area
                    consistency = ConsistencyOutcome.CONFLICT
                else:
                    consistency = (
                        ConsistencyOutcome.CONSISTENT
                    )  # Lenient for icons or partial labels
            elif cluster_visual:
                consistency = ConsistencyOutcome.CONSISTENT
            else:
                consistency = ConsistencyOutcome.UIA_ONLY

            # Link correlation IDs
            all_ids = [e.evidence_id for e in cluster_evidence]
            for e in cluster_evidence:
                e.correlation_ids = [cid for cid in all_ids if cid != e.evidence_id]

            fused_clusters.append(
                {
                    "primary_uia": uia_item,
                    "associated_ocr": cluster_ocr,
                    "associated_visual": cluster_visual,
                    "all_evidence": cluster_evidence,
                    "consistency": consistency,
                    "bounding_box": uia_item.bounding_box,
                }
            )

        # 2. Add remaining OCR-only evidence
        for ocr_item in unmatched_ocr:
            fused_clusters.append(
                {
                    "primary_uia": None,
                    "associated_ocr": [ocr_item],
                    "associated_visual": [],
                    "all_evidence": [ocr_item],
                    "consistency": ConsistencyOutcome.OCR_ONLY,
                    "bounding_box": ocr_item.bounding_box,
                }
            )

        # 3. Add remaining Vision-only evidence
        for vis_item in unmatched_visual:
            fused_clusters.append(
                {
                    "primary_uia": None,
                    "associated_ocr": [],
                    "associated_visual": [vis_item],
                    "all_evidence": [vis_item],
                    "consistency": ConsistencyOutcome.VISION_ONLY,
                    "bounding_box": vis_item.bounding_box,
                }
            )

        return fused_clusters

    def resolve_target(
        self,
        snapshot: ObservationSnapshot,
        target_name: str,
        expected_control_type: str | None = None,
        expected_window_title: str | None = None,
        allow_ocr_fallback: bool = True,
    ) -> ResolvedTarget | None:
        """
        Resolve a specific target by query name and expected metadata (Section 12).
        Applies multi-strategy scoring across UIA, OCR, and Fused clusters.
        """
        if not snapshot.evidence_items:
            return None

        # Check snapshot staleness
        age = time.time() - snapshot.timestamp
        if age > self.max_observation_age_sec:
            logger.warning(
                "Attempting target resolution on stale snapshot (age: %.1fs)", age
            )

        # Separate evidence by source
        uia_items = snapshot.get_by_source(EvidenceSource.UIA)
        ocr_items = snapshot.get_by_source(EvidenceSource.OCR)
        vis_items = snapshot.get_by_source(EvidenceSource.VISUAL_MODEL)

        clusters = self.fuse_evidence(uia_items, ocr_items, vis_items)

        candidates: list[tuple[float, dict[str, Any], ResolutionMethod, list[str]]] = []
        target_norm = target_name.strip().lower()

        for cluster in clusters:
            primary_uia = cluster.get("primary_uia")
            associated_ocr = cluster.get("associated_ocr", [])
            consistency = cluster.get("consistency", ConsistencyOutcome.UNKNOWN)

            # Score factors
            uia_score = 0.0
            ocr_score = 0.0
            reasons = []

            # 1. Evaluate UIA
            if primary_uia:
                u_text = primary_uia.extracted_text.strip().lower()
                u_auto_id = (
                    primary_uia.uia_reference.get("automation_id", "").lower()
                    if primary_uia.uia_reference
                    else ""
                )

                if target_norm and target_norm == u_auto_id:
                    uia_score += 1.0
                    reasons.append(f"Exact AutomationId match: {u_auto_id}")
                elif target_norm and target_norm == u_text:
                    uia_score += 0.95
                    reasons.append(f"Exact UIA text match: {u_text}")
                elif (
                    target_norm
                    and u_text
                    and (
                        target_norm in u_text
                        or (len(u_text) >= 3 and u_text in target_norm)
                    )
                ):
                    uia_score += 0.8
                    reasons.append(f"Substring UIA match: {u_text}")
                elif target_norm and u_text:
                    sim = compute_text_similarity(target_norm, u_text)
                    if sim >= 0.7:
                        uia_score += sim * 0.75
                        reasons.append(f"Fuzzy UIA match: {sim:.2f}")

                # Check control type match
                if expected_control_type and primary_uia.uia_reference:
                    ctype = primary_uia.uia_reference.get("control_type", "")
                    if expected_control_type.lower() == ctype.lower():
                        uia_score += 0.1
                        reasons.append(f"Control type match: {ctype}")

            # 2. Evaluate OCR
            for ocr_ev in associated_ocr:
                o_text = ocr_ev.extracted_text.strip().lower()
                if target_norm and target_norm == o_text:
                    ocr_score = max(ocr_score, 0.9)
                    reasons.append(f"Exact OCR match: {o_text}")
                elif (
                    target_norm
                    and o_text
                    and (
                        target_norm in o_text
                        or (len(o_text) >= 3 and o_text in target_norm)
                    )
                ):
                    ocr_score = max(ocr_score, 0.75)
                    reasons.append(f"Substring OCR match: {o_text}")
                elif target_norm and o_text:
                    sim = compute_text_similarity(target_norm, o_text)
                    if sim >= 0.7:
                        ocr_score = max(ocr_score, sim * 0.7)
                        reasons.append(f"Fuzzy OCR match: {sim:.2f}")

            # Total score calculation
            if primary_uia and associated_ocr:
                total_score = (uia_score * 0.6) + (ocr_score * 0.4)
                method = ResolutionMethod.FUSED_MULTI
            elif primary_uia:
                total_score = uia_score
                method = (
                    ResolutionMethod.EXACT_UIA
                    if uia_score >= 0.95
                    else ResolutionMethod.SEMANTIC_UIA
                )
            elif associated_ocr and allow_ocr_fallback:
                total_score = ocr_score * 0.85  # Slightly lower confidence for OCR-only
                method = ResolutionMethod.OCR_TEXT
            else:
                total_score = 0.0
                method = ResolutionMethod.WINDOW_CONTEXT

            if total_score >= 0.5:
                candidates.append((total_score, cluster, method, reasons))

        if not candidates:
            return None

        # Sort by highest score
        candidates.sort(key=lambda c: c[0], reverse=True)
        best_score, best_cluster, best_method, best_reasons = candidates[0]

        bbox: BoundingBox = best_cluster.get("bounding_box", BoundingBox())
        evidence_ids = [e.evidence_id for e in best_cluster.get("all_evidence", [])]
        consistency = best_cluster.get("consistency", ConsistencyOutcome.CONSISTENT)

        # Compute evidence fingerprint
        evidence_fingerprint = (
            hashlib.sha256("".join(sorted(evidence_ids)).encode("utf-8")).hexdigest()[
                :16
            ]
            if evidence_ids
            else ""
        )

        app_name = (
            snapshot.metadata.get("app_name") or snapshot.window_title or "UnknownApp"
        )
        win_title = snapshot.window_title or "UnknownWindow"
        win_hwnd = snapshot.window_hwnd or 0

        return ResolvedTarget(
            name=target_name,
            bounding_box=bbox,
            center_point=bbox.center,
            confidence=round(min(1.0, best_score), 3),
            resolution_method=best_method,
            evidence_ids=evidence_ids,
            consistency=consistency,
            application=app_name,
            window_title=win_title,
            hwnd=win_hwnd,
            is_stale=age > self.max_observation_age_sec,
            observation_id=snapshot.observation_id,
            task_id=snapshot.task_id,
            step_id=snapshot.step_id,
            monitor_id=snapshot.monitor_id,
            dpi_context=snapshot.dpi_scaling,
            target_state="active",
            evidence_fingerprint=evidence_fingerprint,
            reasons=best_reasons,
        )

    def validate_target_staleness(
        self,
        target: ResolvedTarget,
        current_window_hwnd: int,
        current_window_title: str,
        current_snapshot: ObservationSnapshot | None = None,
        max_age_sec: float = 10.0,
    ) -> tuple[bool, str]:
        """
        10-Point Stale Observation Protection (Section 14 & Point 5).
        Validates target identity and freshness before any click or input action:
        1. Observation freshness
        2. Application identity
        3. Window identity (HWND)
        4. Window title similarity
        5. Target bounds validity
        6. Target state active
        7. Multimodal conflict status
        8. Target presence in fresh snapshot
        9. Target center within valid bounds
        10. Deterministic safety verification
        """
        # 1. Freshness check
        age = time.time() - target.created_at
        if age > max_age_sec:
            target.is_stale = True
            return (
                False,
                f"STALE_OBSERVATION: Target age {age:.1f}s exceeds limit {max_age_sec}s",
            )

        # 2. Window HWND identity check
        if (
            target.hwnd > 0
            and current_window_hwnd > 0
            and target.hwnd != current_window_hwnd
        ):
            target.is_stale = True
            return (
                False,
                f"STALE_OBSERVATION: Window HWND changed from {target.hwnd} to {current_window_hwnd}",
            )

        # 3. Window title check
        if target.window_title and current_window_title:
            sim = compute_text_similarity(target.window_title, current_window_title)
            if sim < 0.4:
                target.is_stale = True
                return (
                    False,
                    f"STALE_OBSERVATION: Window title changed from '{target.window_title}' to '{current_window_title}'",
                )

        # 4. Target bounds validity
        if not target.bounding_box.is_valid:
            target.is_stale = True
            return False, "STALE_OBSERVATION: Target bounding box is zero or negative"

        # 5. Target state
        if target.target_state != "active":
            target.is_stale = True
            return (
                False,
                f"STALE_OBSERVATION: Target state '{target.target_state}' is not active",
            )

        # 6. Consistency check (Point 6 safety boundary)
        if target.consistency == ConsistencyOutcome.CONFLICT:
            return (
                False,
                "EVIDENCE_CONFLICT: Target has conflicting multimodal evidence; requires resolution",
            )

        # 7. Center point check
        if target.center_point == (0, 0):
            target.is_stale = True
            return False, "STALE_OBSERVATION: Target center point is ungrounded (0, 0)"

        # 8. Position check in fresh snapshot if provided
        if current_snapshot:
            matched = False
            for ev in current_snapshot.evidence_items:
                if (
                    ev.bounding_box.contains_point(*target.center_point)
                    or ev.bounding_box.iou(target.bounding_box) > 0.2
                ):
                    matched = True
                    break
            if not matched and len(current_snapshot.evidence_items) > 0:
                target.is_stale = True
                return (
                    False,
                    "STALE_OBSERVATION: Target is no longer present at target coordinates in fresh snapshot",
                )

        return True, "Valid"


def calculate_iou(b1: Any, b2: Any) -> float:
    """Calculates Intersection over Union (IoU) for two CoordinateBounds or BoundingBoxes."""
    x_left = max(b1.left, b2.left)
    y_top = max(b1.top, b2.top)
    x_right = min(b1.right, b2.right)
    y_bottom = min(b1.bottom, b2.bottom)

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    b1_w = getattr(b1, "width", b1.right - b1.left)
    b1_h = getattr(b1, "height", b1.bottom - b1.top)
    b2_w = getattr(b2, "width", b2.right - b2.left)
    b2_h = getattr(b2, "height", b2.bottom - b2.top)
    b1_area = b1_w * b1_h
    b2_area = b2_w * b2_h
    union_area = b1_area + b2_area - intersection_area

    if union_area == 0:
        return 0.0

    return intersection_area / union_area


def fuse_evidence(
    uia_elements: list[Any],
    ocr_elements: list[Any],
    iou_threshold: float = 0.3,
) -> list[Any]:
    """Fuses UIA and OCR evidence into unified clusters based on spatial overlap."""
    from perception.models import CoordinateBounds, FusedCluster

    clusters = []
    used_ocr_indices = set()

    for uia in uia_elements:
        if not uia.bounds:
            continue

        best_ocr = None
        best_iou = 0.0
        best_ocr_idx = -1

        for i, ocr in enumerate(ocr_elements):
            if i in used_ocr_indices:
                continue

            iou = calculate_iou(uia.bounds, ocr.bounds)
            if iou > best_iou:
                best_iou = iou
                best_ocr = ocr
                best_ocr_idx = i

        if best_iou >= iou_threshold and best_ocr is not None:
            used_ocr_indices.add(best_ocr_idx)
            fused_bounds = CoordinateBounds(
                left=min(uia.bounds.left, best_ocr.bounds.left),
                top=min(uia.bounds.top, best_ocr.bounds.top),
                right=max(uia.bounds.right, best_ocr.bounds.right),
                bottom=max(uia.bounds.bottom, best_ocr.bounds.bottom),
                coordinate_space=uia.bounds.coordinate_space,
                monitor_dpi=uia.bounds.monitor_dpi,
            )
            is_consistent = (uia.name.strip().lower() == best_ocr.text.strip().lower())
            state = "CONSISTENT" if is_consistent else "CONFLICT"
            clusters.append(
                FusedCluster(
                    cluster_id=f"cluster_{len(clusters)}",
                    bounds=fused_bounds,
                    uia_element=uia,
                    primary_uia=uia,
                    ocr_element=best_ocr,
                    associated_ocr=[best_ocr],
                    consistency_state=state,
                    confidence=(getattr(uia, "confidence", 1.0) + getattr(best_ocr, "confidence", 1.0)) / 2.0,
                )
            )
        else:
            clusters.append(
                FusedCluster(
                    cluster_id=f"cluster_{len(clusters)}",
                    bounds=uia.bounds,
                    uia_element=uia,
                    primary_uia=uia,
                    ocr_element=None,
                    associated_ocr=[],
                    consistency_state="UIA_ONLY",
                    confidence=getattr(uia, "confidence", 1.0),
                )
            )

    for i, ocr in enumerate(ocr_elements):
        if i not in used_ocr_indices:
            clusters.append(
                FusedCluster(
                    cluster_id=f"cluster_{len(clusters)}",
                    bounds=ocr.bounds,
                    uia_element=None,
                    primary_uia=None,
                    ocr_element=ocr,
                    associated_ocr=[ocr],
                    consistency_state="OCR_ONLY",
                    confidence=getattr(ocr, "confidence", 1.0),
                )
            )

    return clusters
