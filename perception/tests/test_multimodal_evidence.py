from datetime import datetime

from perception.models import (
    CoordinateBounds,
    CoordinateSpace,
    FusedCluster,
    MultimodalEvidence,
    OcrElement,
    TemporalDelta,
    UiaElement,
)


def test_coordinate_bounds():
    bounds = CoordinateBounds(left=10, top=20, right=100, bottom=50)
    assert bounds.width == 90
    assert bounds.height == 30
    assert bounds.coordinate_space == CoordinateSpace.LOGICAL
    assert bounds.monitor_dpi is None


def test_temporal_delta():
    delta = TemporalDelta(
        pre_hash="hash1",
        post_hash="hash2",
        diff_ratio=0.15,
        transition_type="TARGET_APPEARED",
    )
    assert delta.pre_hash == "hash1"
    assert delta.post_hash == "hash2"
    assert delta.diff_ratio == 0.15
    assert delta.transition_type == "TARGET_APPEARED"


def test_multimodal_evidence_creation():
    bounds = CoordinateBounds(left=0, top=0, right=100, bottom=100)
    ocr = OcrElement(text="Submit", bounds=bounds, confidence=0.95)
    uia = UiaElement(name="Submit", control_type="Button", bounds=bounds)

    cluster = FusedCluster(
        bounds=bounds, ocr_element=ocr, uia_element=uia, consistency_state="CONSISTENT"
    )

    evidence = MultimodalEvidence(
        id="ev_001",
        hwnd=12345,
        window_title="Test App",
        uia_elements=[uia],
        ocr_elements=[ocr],
        fused_clusters=[cluster],
    )

    assert evidence.id == "ev_001"
    assert evidence.hwnd == 12345
    assert evidence.window_title == "Test App"
    assert len(evidence.uia_elements) == 1
    assert len(evidence.ocr_elements) == 1
    assert len(evidence.fused_clusters) == 1

    # Test datetime factory
    assert isinstance(evidence.timestamp, datetime)
