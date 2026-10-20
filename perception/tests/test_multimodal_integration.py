"""
Integration tests for Phase 7 Multimodal Perception Service & Execution Controller.
Validates the full perception loop, target grounding, temporal verification,
AI_UNAVAILABLE fallback, and truthful multimodal SSE events.
"""

from unittest.mock import patch

from backend.app.services.task_service import task_service
from perception.models_multimodal import (
    BoundingBox,
    CapabilityStatus,
    EvidenceSource,
    MultimodalEvidence,
    ObservationSnapshot,
)
from perception.multimodal_service import MultimodalPerceptionService
from perception.ocr_engine import MockOcrBackend, OCREngineManager
from perception.vision_router import VisionRouter
from planner.execution_controller import MultiStepExecutionController


def test_multimodal_service_full_snapshot_and_target_resolution(tmp_path):
    """Verify MultimodalPerceptionService extracts UIA, OCR, fuses evidence, and resolves targets."""
    mock_ocr = MockOcrBackend(
        predefined_results=[
            {
                "text": "Save Document",
                "box": {"left": 20, "top": 40, "width": 80, "height": 25},
                "confidence": 0.95,
            },
            {
                "text": "Discard",
                "box": {"left": 120, "top": 40, "width": 60, "height": 25},
                "confidence": 0.90,
            },
        ]
    )
    ocr_mgr = OCREngineManager(preferred_backend=mock_ocr)
    service = MultimodalPerceptionService(ocr_manager=ocr_mgr)

    # Capture multimodal snapshot
    snapshot = service.capture_multimodal_snapshot(
        task_id="task_test_1", step_id="step_1", include_ocr=True
    )
    assert isinstance(snapshot, ObservationSnapshot)
    assert snapshot.task_id == "task_test_1"
    assert len(snapshot.evidence_items) >= 2

    # Target resolution for "Save Document"
    target = service.resolve_target(snapshot, target_name="Save Document")
    assert target is not None
    assert "Save" in target.name
    assert target.center_point != (0, 0)
    assert target.is_stale is False


def test_vision_router_ai_unavailable_fallback():
    """Verify VisionRouter safely emits AI_UNAVAILABLE when no vision model is registered (Section 18)."""
    router = VisionRouter(omniroute_manager=None)
    assert router.is_vision_model_available() is False
    assert router.get_capability_status() == CapabilityStatus.UNAVAILABLE

    status, answer, ev = router.analyze_screenshot("dummy.png", "what is on screen?")
    assert status == CapabilityStatus.UNAVAILABLE
    assert answer is None
    assert ev == []


def test_multimodal_verification_state_change():
    """Verify verify_multimodal_state_change detects expected text and target disappearance."""
    service = MultimodalPerceptionService()

    obs_before = ObservationSnapshot(
        observation_id="before_1", window_title="Untitled - Notepad", timestamp=10.0
    )
    obs_before.evidence_items.append(
        MultimodalEvidence(
            source=EvidenceSource.OCR,
            extracted_text="Save As Dialog",
            bounding_box=BoundingBox.from_ltwh(50, 50, 60, 20),
        )
    )

    obs_after = ObservationSnapshot(
        observation_id="after_1", window_title="Untitled - Notepad", timestamp=12.0
    )
    # Target "Save As Dialog" dismissed, new text appeared
    obs_after.evidence_items.append(
        MultimodalEvidence(
            source=EvidenceSource.OCR,
            extracted_text="File Saved Successfully",
            bounding_box=BoundingBox.from_ltwh(50, 50, 100, 20),
        )
    )

    # Verification for target disappearance
    v_res = service.verify_multimodal_state_change(
        obs_before, obs_after, expected_target_name="Save As Dialog"
    )
    assert v_res.verified is True
    assert v_res.confidence >= 0.85

    # Verification for expected text
    v_text = service.verify_multimodal_state_change(
        obs_before, obs_after, expected_text="File Saved Successfully"
    )
    assert v_text.verified is True
    assert v_text.confidence >= 0.9


def test_multimodal_execution_controller_events():
    """Verify execution controller emits multimodal perception and verification SSE events."""
    mock_ocr = MockOcrBackend(
        predefined_results=[
            {
                "text": "OK",
                "box": {"left": 10, "top": 10, "width": 40, "height": 20},
                "confidence": 0.95,
            }
        ]
    )
    ocr_mgr = OCREngineManager(preferred_backend=mock_ocr)
    service = MultimodalPerceptionService(ocr_manager=ocr_mgr)

    controller = MultiStepExecutionController(perception_service=service)
    task = task_service.create_task("Test Multimodal Events")
    tid = task["id"]

    events = []

    def on_event(ev_type, payload):
        events.append(ev_type)

    with patch(
        "automation.action_dispatcher.type_text", return_value={"success": True}
    ), patch(
        "perception.uia_inspector.get_foreground_window",
        return_value={"success": True, "window": {"title": "Notepad"}},
    ):
        res = controller.run_multistep_task(  # noqa: F841
            tid, "Open Notepad then type text", on_event=on_event
        )

    # Verify Phase 7 events occurred
    assert "perception_started" in events
    assert "ocr_completed" in events
    assert "evidence_fused" in events
    assert "verification_started" in events
    assert "verification_completed" in events
