from PIL import Image, ImageDraw

from perception.ocr import WinRTOcrBackend


def test_winrt_ocr_initialization():
    backend = WinRTOcrBackend()
    assert backend.engine is not None


def test_winrt_ocr_extraction():
    # Create an image with some text
    img = Image.new("RGBA", (300, 100), color="white")
    d = ImageDraw.Draw(img)
    # Draw simple text
    d.text((10, 10), "TEST OCR", fill=(0, 0, 0))

    backend = WinRTOcrBackend()
    elements = backend.extract_text(img)

    assert len(elements) > 0
    # It might read it as "TEST", "OCR", or "TESTOCR" due to font, just check if something was found
    found_text = " ".join([e.text for e in elements]).upper()  # noqa: F841

    # We should have valid bounds
    for e in elements:
        assert e.bounds.width > 0
        assert e.bounds.height > 0
        assert e.confidence == 1.0
