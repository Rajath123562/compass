import os
import tempfile

from PIL import Image, ImageDraw

from perception.security import ScreenshotRingBuffer, redact_text
from perception.temporal import calculate_image_diff_ratio, detect_transition_type


def test_image_diff():
    # Two identical images
    img1 = Image.new("RGB", (100, 100), color="white")
    img2 = Image.new("RGB", (100, 100), color="white")

    ratio = calculate_image_diff_ratio(img1, img2)
    assert ratio == 0.0
    assert detect_transition_type(ratio) == "UNCHANGED"

    # Completely different images (black vs white)
    img3 = Image.new("RGB", (100, 100), color="black")
    ratio2 = calculate_image_diff_ratio(img1, img3)
    assert ratio2 == 1.0
    assert detect_transition_type(ratio2) == "SIGNIFICANT_SCREEN_CHANGE"

    # Slightly different image
    img4 = Image.new("RGB", (100, 100), color="white")
    d = ImageDraw.Draw(img4)
    d.rectangle((0, 0, 10, 10), fill="black")  # 100 pixels out of 10000 = 0.01

    ratio3 = calculate_image_diff_ratio(img1, img4)
    assert round(ratio3, 3) == 0.012
    assert detect_transition_type(ratio3, threshold=0.05) == "MINOR_SCREEN_CHANGE"


def test_redact_text():
    # OpenAI key
    text1 = "Here is my key sk-dummy123456789012345678901234567890123456789012345678 dont steal it"
    assert "sk-" not in redact_text(text1)
    assert "[REDACTED]" in redact_text(text1)

    # GitHub PAT
    text2 = "ghp_dummy123456789012345678901234567890123456"
    assert "ghp_" not in redact_text(text2)
    assert "[REDACTED]" in redact_text(text2)

    # Bearer
    text3 = "Authorization: Bearer dummy_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ"
    assert "Bearer" not in redact_text(text3)

    # Normal text
    text4 = "No secrets here!"
    assert redact_text(text4) == text4


def test_ring_buffer():
    with tempfile.TemporaryDirectory() as tmpdir:
        buffer = ScreenshotRingBuffer(directory=tmpdir, max_files=3)

        # Create 5 files
        files = []
        for i in range(5):
            path = os.path.join(tmpdir, f"test_{i}.png")
            Image.new("RGB", (10, 10)).save(path)
            files.append(path)
            buffer.add_screenshot(path)

        # Since max_files=3, the first 2 should be deleted
        assert not os.path.exists(files[0])
        assert not os.path.exists(files[1])
        assert os.path.exists(files[2])
        assert os.path.exists(files[3])
        assert os.path.exists(files[4])

        # Cleanup
        buffer.cleanup()
        for f in files[2:]:
            assert not os.path.exists(f)
