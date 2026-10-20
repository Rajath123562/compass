from perception.fusion import calculate_iou, fuse_evidence
from perception.models import CoordinateBounds, OcrElement, UiaElement


def test_calculate_iou():
    b1 = CoordinateBounds(left=0, top=0, right=100, bottom=100)
    b2 = CoordinateBounds(left=50, top=50, right=150, bottom=150)

    iou = calculate_iou(b1, b2)

    # Intersection is 50x50 = 2500
    # Union is 10000 + 10000 - 2500 = 17500
    # IoU = 2500 / 17500 = 0.1428...
    assert round(iou, 4) == 0.1429

    # Complete overlap
    assert calculate_iou(b1, b1) == 1.0

    # No overlap
    b3 = CoordinateBounds(left=200, top=200, right=300, bottom=300)
    assert calculate_iou(b1, b3) == 0.0


def test_fuse_evidence():
    uia1 = UiaElement(
        name="Submit",
        control_type="Button",
        bounds=CoordinateBounds(left=10, top=10, right=100, bottom=40),
    )
    uia2 = UiaElement(
        name="Cancel",
        control_type="Button",
        bounds=CoordinateBounds(left=120, top=10, right=200, bottom=40),
    )

    # Exactly matching Submit
    ocr1 = OcrElement(
        text="Submit", bounds=CoordinateBounds(left=12, top=12, right=98, bottom=38)
    )
    # Some other text nowhere near UIA
    ocr2 = OcrElement(
        text="Logo", bounds=CoordinateBounds(left=500, top=10, right=600, bottom=50)
    )

    clusters = fuse_evidence([uia1, uia2], [ocr1, ocr2])

    assert len(clusters) == 3

    # Check "Submit" cluster (CONSISTENT)
    submit_cluster = next(
        (c for c in clusters if c.uia_element and c.uia_element.name == "Submit"), None
    )
    assert submit_cluster is not None
    assert submit_cluster.consistency_state == "CONSISTENT"
    assert submit_cluster.ocr_element.text == "Submit"

    # Check "Cancel" cluster (UIA_ONLY)
    cancel_cluster = next(
        (c for c in clusters if c.uia_element and c.uia_element.name == "Cancel"), None
    )
    assert cancel_cluster is not None
    assert cancel_cluster.consistency_state == "UIA_ONLY"
    assert cancel_cluster.ocr_element is None

    # Check "Logo" cluster (OCR_ONLY)
    logo_cluster = next(
        (c for c in clusters if c.ocr_element and c.ocr_element.text == "Logo"), None
    )
    assert logo_cluster is not None
    assert logo_cluster.consistency_state == "OCR_ONLY"
    assert logo_cluster.uia_element is None
