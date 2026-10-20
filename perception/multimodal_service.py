"""
COMPASS Phase 7 — Unified Multimodal Perception Service
Coordinates Screen Capture, UIA Inspection, WinRT/Tesseract OCR, Coordinate Mapping,
Cross-Modal Evidence Fusion, Temporal Perception, and Privacy/Security Ring Buffer.
"""

from __future__ import annotations

import ctypes
import hashlib
import logging
import sys
import time
from pathlib import Path

user32 = ctypes.windll.user32 if sys.platform == "win32" else None

from perception import screen_capture, uia_inspector
from perception.coordinate_mapper import CoordinateMapper
from perception.evidence_fusion import EvidenceFusionEngine
from perception.models_multimodal import (
    CAPABILITY_TAXONOMY_DEFAULT,
    BoundingBox,
    CapabilityStatus,
    CoordinateSpace,
    EvidenceProvenance,
    EvidenceSource,
    MultimodalEvidence,
    MultimodalVerificationResult,
    ObservationSnapshot,
    ResolvedTarget,
)
from perception.ocr_engine import OCREngineManager
from perception.perception_security import (
    CredentialRedactor,
    ScreenshotRingBuffer,
    UntrustedContentQuarantine,
)
from perception.temporal_comparator import StateTransitionType, TemporalComparator
from perception.vision_router import VisionRouter

logger = logging.getLogger(__name__)


class MultimodalPerceptionService:
    """
    Authoritative Phase 7 Perception Coordinator.
    Ensures safe, truthful, multi-evidence perception across Windows digital interfaces.
    """

    def __init__(
        self,
        ocr_manager: OCREngineManager | None = None,
        ring_buffer: ScreenshotRingBuffer | None = None,
        vision_router: VisionRouter | None = None,
    ):
        self.ocr_manager = ocr_manager or OCREngineManager()
        self.ring_buffer = ring_buffer or ScreenshotRingBuffer()
        self.coord_mapper = CoordinateMapper()
        self.temporal_comparator = TemporalComparator()
        self.fusion_engine = EvidenceFusionEngine()
        self.vision_router = vision_router or VisionRouter()
        self._last_snapshot: ObservationSnapshot | None = None

    def get_capabilities(self) -> dict[str, CapabilityStatus]:
        """Return truthful capability taxonomy statuses (Section 6)."""
        caps = dict(CAPABILITY_TAXONOMY_DEFAULT)
        # Update dynamic capabilities
        caps["OCR"] = self.ocr_manager.get_capability_status()
        caps["image_understanding"] = self.vision_router.get_capability_status()
        return caps

    def capture_multimodal_snapshot(
        self,
        task_id: str = "",
        step_id: str = "",
        include_ocr: bool = True,
        include_vision: bool = False,
        capture_full_desktop: bool = False,
        image_path: str | None = None,
        target_hwnd: int | None = None,
    ) -> ObservationSnapshot:
        """
        Capture a fresh multimodal observation snapshot of the active Windows interface.
        Extracts UIA elements, captures pixels, executes WinRT OCR, and tracks provenance.
        """
        t0 = time.time()

        # 1. Foreground / Target window state
        hwnd = 0
        window_title = "Desktop"
        win_bounds = BoundingBox.from_ltwh(0, 0, 1920, 1080)

        if target_hwnd and user32.IsWindow(target_hwnd):
            hwnd = target_hwnd
            import ctypes

            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            window_title = buf.value or "Window"
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            win_bounds = BoundingBox(
                left=rect.left,
                top=rect.top,
                right=rect.right,
                bottom=rect.bottom,
                coordinate_space=CoordinateSpace.SCREEN_PHYSICAL,
            )
        else:
            fw = uia_inspector.get_foreground_window()
            if fw.get("window"):
                w_info = fw["window"]
                hwnd = w_info.get("hwnd", 0)
                window_title = w_info.get("title", "") or "Desktop"
                wb = w_info.get("bounds", {})
                win_bounds = BoundingBox.from_ltwh(
                    wb.get("left", 0),
                    wb.get("top", 0),
                    wb.get("width", 1920),
                    wb.get("height", 1080),
                    CoordinateSpace.SCREEN_PHYSICAL,
                )

        # 2. Screen capture
        screenshot_path = None
        screenshot_hash = None
        offset_x = win_bounds.left
        offset_y = win_bounds.top

        if image_path and Path(image_path).exists():
            screenshot_path = self.ring_buffer.register_screenshot(image_path)
            try:
                with open(screenshot_path, "rb") as f:
                    screenshot_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:  # noqa: BLE001
                screenshot_hash = None
        else:
            capture_dir = self.ring_buffer.base_dir
            if capture_full_desktop:
                cap_res = screen_capture.capture_full_screen(
                    save_dir=capture_dir, include_b64=False
                )
                offset_x = 0
                offset_y = 0
            elif target_hwnd and user32.IsWindow(target_hwnd):
                cap_res = screen_capture.capture_window(
                    target_hwnd, save_dir=capture_dir, include_b64=False
                )
            else:
                cap_res = screen_capture.capture_foreground_window(
                    save_dir=capture_dir, include_b64=False
                )
                offset_x = win_bounds.left
                offset_y = win_bounds.top

            if cap_res.success and cap_res.png_path:
                screenshot_path = self.ring_buffer.register_screenshot(cap_res.png_path)
                try:
                    with open(screenshot_path, "rb") as f:
                        screenshot_hash = hashlib.sha256(f.read()).hexdigest()
                except Exception:  # noqa: BLE001
                    screenshot_hash = None

        # 3. UIA Tree extraction
        uia_evidence: list[MultimodalEvidence] = []
        if hwnd:
            tree_res = uia_inspector.get_element_tree(
                hwnd=hwnd, depth=3, max_elements=150
            )
            if tree_res.get("success") and tree_res.get("elements"):
                for el in tree_res["elements"]:
                    b = el.get("bounds", {})
                    box = BoundingBox.from_ltwh(
                        b.get("left", 0),
                        b.get("top", 0),
                        b.get("width", 0),
                        b.get("height", 0),
                        CoordinateSpace.SCREEN_PHYSICAL,
                    )
                    text_content = el.get("name") or el.get("text") or ""
                    prov = EvidenceProvenance(
                        source=EvidenceSource.UIA,
                        source_version="UIA-3.0",
                        capture_hash=screenshot_hash,
                        device_context={
                            "hwnd": hwnd,
                            "control_type": el.get("control_type"),
                        },
                    )
                    uia_evidence.append(
                        MultimodalEvidence(
                            task_id=task_id,
                            step_id=step_id,
                            source=EvidenceSource.UIA,
                            application=window_title,
                            window_title=window_title,
                            hwnd=hwnd,
                            bounding_box=box,
                            extracted_text=text_content,
                            confidence=1.0,  # Deterministic UIA
                            provenance=prov,
                            uia_reference={
                                "automation_id": el.get("automation_id", ""),
                                "runtime_id": el.get("runtime_id", ""),
                                "control_type": el.get("control_type", ""),
                                "class_name": el.get("class_name", ""),
                            },
                            is_untrusted=False,
                        )
                    )

        # 4. OCR Extraction & Sanitization
        ocr_evidence: list[MultimodalEvidence] = []
        if include_ocr:
            from perception.ocr_engine import MockOcrBackend

            target_img = screenshot_path
            if not target_img and isinstance(
                self.ocr_manager.active_backend, MockOcrBackend
            ):
                target_img = "mock_test_image.png"

            raw_ocr = []
            if target_img:
                raw_ocr = self.ocr_manager.extract(
                    target_img, offset_x=offset_x, offset_y=offset_y, timeout_sec=6.0
                )
            for item in raw_ocr:
                # Quarantining & Credential Redaction (Sections 17, 26)
                raw_text = item.extracted_text
                sanitized_text = UntrustedContentQuarantine.sanitize_untrusted_text(
                    raw_text
                )
                redacted_text = CredentialRedactor.redact(sanitized_text)

                item.task_id = task_id
                item.step_id = step_id
                item.application = window_title
                item.window_title = window_title
                item.hwnd = hwnd
                item.extracted_text = redacted_text
                item.provenance.capture_hash = screenshot_hash
                ocr_evidence.append(item)

        # 5. Optional Vision model extraction
        visual_evidence: list[MultimodalEvidence] = []
        if include_vision and screenshot_path:
            v_status, v_text, v_evidence = self.vision_router.analyze_screenshot(  # noqa: RUF059
                screenshot_path, query="Detect primary interactive buttons and controls"
            )
            if v_status == CapabilityStatus.AVAILABLE:
                visual_evidence.extend(v_evidence)

        # 6. Fuse all evidence
        all_evidence = uia_evidence + ocr_evidence + visual_evidence
        # Correlate and link items
        self.fusion_engine.fuse_evidence(uia_evidence, ocr_evidence, visual_evidence)

        # Identify primary monitor
        mon_info = self.coord_mapper.get_monitor_for_point(
            win_bounds.left, win_bounds.top
        )
        mon_id = mon_info.monitor_id if mon_info else 0
        dpi_scale = mon_info.scale_factor if mon_info else 1.0

        snapshot = ObservationSnapshot(
            task_id=task_id,
            step_id=step_id,
            monitor_id=mon_id,
            dpi_scaling=dpi_scale,
            screenshot_path=screenshot_path,
            screenshot_hash=screenshot_hash,
            window_hwnd=hwnd,
            window_title=window_title,
            window_bounds=win_bounds,
            evidence_items=all_evidence,
            metadata={
                "capture_latency_ms": round((time.time() - t0) * 1000, 1),
                "uia_count": len(uia_evidence),
                "ocr_count": len(ocr_evidence),
                "visual_count": len(visual_evidence),
            },
        )

        for ev in snapshot.evidence_items:
            ev.observation_id = snapshot.observation_id

        self._last_snapshot = snapshot
        return snapshot

    def resolve_target(
        self,
        snapshot: ObservationSnapshot,
        target_name: str,
        expected_control_type: str | None = None,
        allow_ocr_fallback: bool = True,
    ) -> ResolvedTarget | None:
        """Resolve a specific target by query name and expected metadata."""
        return self.fusion_engine.resolve_target(
            snapshot=snapshot,
            target_name=target_name,
            expected_control_type=expected_control_type,
            expected_window_title=snapshot.window_title,
            allow_ocr_fallback=allow_ocr_fallback,
        )

    def verify_multimodal_state_change(
        self,
        obs_before: ObservationSnapshot,
        obs_after: ObservationSnapshot,
        expected_target_name: str | None = None,
        expected_window_title: str | None = None,
        expected_text: str | None = None,
    ) -> MultimodalVerificationResult:
        """
        Multimodal state verification combining visual diff, OCR text presence,
        and temporal transitions (Section 22).
        """
        t_res = self.temporal_comparator.compare_observations(
            obs_before, obs_after, expected_target_name=expected_target_name
        )

        verified = False
        confidence = 0.0
        details = dict(t_res.details)
        discrepancies: list[str] = []
        evidence_used = [obs_before.observation_id, obs_after.observation_id]

        # 1. Target disappeared (e.g. click dismissed dialog or closed menu)
        if expected_target_name and t_res.has_transition(
            StateTransitionType.TARGET_DISAPPEARED
        ):
            verified = True
            confidence = max(confidence, 0.9)
            details["verified_target_disappeared"] = True

        # 2. Significant visual pixel difference
        if t_res.has_transition(StateTransitionType.SIGNIFICANT_SCREEN_CHANGE):
            details["screen_change_detected"] = True
            confidence = max(confidence, 0.75)

        # 3. Expected text presence in obs_after via OCR
        if expected_text:
            text_norm = expected_text.strip().lower()
            text_found = any(
                text_norm in e.extracted_text.lower() for e in obs_after.evidence_items
            )
            if text_found:
                verified = True
                confidence = max(confidence, 0.95)
                details["expected_text_found"] = expected_text
            else:
                discrepancies.append(
                    f"Expected text '{expected_text}' not detected in observation after action"
                )

        # 4. Expected window title change
        if expected_window_title:
            if expected_window_title.lower() in obs_after.window_title.lower():
                verified = True
                confidence = max(confidence, 0.95)
                details["expected_window_title_confirmed"] = obs_after.window_title
            else:
                discrepancies.append(
                    f"Expected window title '{expected_window_title}' does not match '{obs_after.window_title}'"
                )

        # If significant visual change happened and no target-specific requirement failed
        if (
            not expected_text
            and not expected_window_title
            and t_res.pixel_difference_ratio > 0.01
        ):
            verified = True
            confidence = 0.8

        return MultimodalVerificationResult(
            verified=verified,
            confidence=round(confidence, 3),
            verification_method="multimodal_temporal_fusion",
            evidence_used=evidence_used,
            details=details,
            discrepancies=discrepancies,
        )
