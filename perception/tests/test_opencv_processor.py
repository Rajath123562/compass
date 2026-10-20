"""
COMPASS — OpenCV Visual Processor Tests
Tests for perception/opencv_processor.py

Tests cover:
  - Module availability detection
  - Screenshot diff (identical, different, missing files)
  - OCR preprocessing
  - Visual region extraction
  - Region comparison
  - Graceful degradation when OpenCV unavailable
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from perception import opencv_processor

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_image_a(tmp_path):
    """Create a simple test image (white 100x100)."""
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        path = tmp_path / "test_a.png"
        img.save(str(path))
        return str(path)
    except ImportError:
        pytest.skip("Pillow required for test image generation")


@pytest.fixture
def sample_image_b(tmp_path):
    """Create a different test image (black 100x100)."""
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(0, 0, 0))
        path = tmp_path / "test_b.png"
        img.save(str(path))
        return str(path)
    except ImportError:
        pytest.skip("Pillow required for test image generation")


@pytest.fixture
def sample_image_identical(tmp_path):
    """Create a second white image identical to sample_image_a."""
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        path = tmp_path / "test_identical.png"
        img.save(str(path))
        return str(path)
    except ImportError:
        pytest.skip("Pillow required for test image generation")


@pytest.fixture
def sample_image_with_shapes(tmp_path):
    """Create a test image with rectangles (simulated buttons)."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 300), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        # Simulate button-like rectangles
        draw.rectangle([50, 50, 200, 90], fill=(0, 120, 215), outline=(0, 0, 0))
        draw.rectangle([50, 120, 200, 160], fill=(0, 120, 215), outline=(0, 0, 0))
        draw.rectangle(
            [250, 50, 370, 90], fill=(200, 200, 200), outline=(100, 100, 100)
        )
        path = tmp_path / "test_shapes.png"
        img.save(str(path))
        return str(path)
    except ImportError:
        pytest.skip("Pillow required for test image generation")


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestAvailability:
    """Test OpenCV availability detection."""

    def test_is_available_returns_bool(self):
        result = opencv_processor.is_available()
        assert isinstance(result, bool)

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_is_available_true_when_installed(self):
        assert opencv_processor.is_available() is True


class TestScreenshotDiff:
    """Test screenshot comparison."""

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_identical_images(self, sample_image_a, sample_image_identical):
        result = opencv_processor.screenshot_diff(
            sample_image_a, sample_image_identical
        )
        assert result.pixel_diff_ratio == 0.0
        assert result.structural_similarity > 0.99
        assert result.changed_region_count == 0

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_different_images(self, sample_image_a, sample_image_b):
        result = opencv_processor.screenshot_diff(sample_image_a, sample_image_b)
        assert result.pixel_diff_ratio > 0.5
        assert result.structural_similarity < 0.5
        assert result.total_changed_pixels > 0

    def test_missing_file_a(self, sample_image_a):
        result = opencv_processor.screenshot_diff(
            "/nonexistent/path.png", sample_image_a
        )
        assert result.pixel_diff_ratio == 0.0

    def test_missing_both_files(self):
        result = opencv_processor.screenshot_diff("/a.png", "/b.png")
        assert result.pixel_diff_ratio == 0.0

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_result_has_computation_time(self, sample_image_a, sample_image_b):
        result = opencv_processor.screenshot_diff(sample_image_a, sample_image_b)
        assert result.computation_ms > 0

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_to_dict(self, sample_image_a, sample_image_b):
        result = opencv_processor.screenshot_diff(sample_image_a, sample_image_b)
        d = result.to_dict()
        assert "pixel_diff_ratio" in d
        assert "structural_similarity" in d
        assert "changed_region_count" in d
        assert "computation_ms" in d


class TestPreprocessForOCR:
    """Test OCR image preprocessing."""

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_preprocess_creates_output(self, sample_image_a, tmp_path):
        out = str(tmp_path / "preprocessed.png")
        result = opencv_processor.preprocess_for_ocr(sample_image_a, output_path=out)
        assert result is not None
        assert Path(result).exists()

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_preprocess_default_output_path(self, sample_image_a):
        result = opencv_processor.preprocess_for_ocr(sample_image_a)
        assert result is not None
        assert "_ocr_preprocessed" in result
        # Cleanup
        if result and Path(result).exists():
            Path(result).unlink()

    def test_preprocess_missing_file(self):
        result = opencv_processor.preprocess_for_ocr("/nonexistent.png")
        assert result is None

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_preprocess_no_denoise(self, sample_image_a, tmp_path):
        out = str(tmp_path / "no_denoise.png")
        result = opencv_processor.preprocess_for_ocr(
            sample_image_a, output_path=out, denoise=False
        )
        assert result is not None


class TestVisualRegionExtraction:
    """Test visual region detection."""

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_extracts_regions_from_shapes(self, sample_image_with_shapes):
        regions = opencv_processor.extract_visual_regions(sample_image_with_shapes)
        assert isinstance(regions, list)
        # The image with drawn rectangles should produce at least 1 region
        assert len(regions) >= 1

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_region_has_correct_fields(self, sample_image_with_shapes):
        regions = opencv_processor.extract_visual_regions(sample_image_with_shapes)
        if regions:
            r = regions[0]
            assert hasattr(r, "x")
            assert hasattr(r, "y")
            assert hasattr(r, "width")
            assert hasattr(r, "height")
            assert hasattr(r, "area")
            assert hasattr(r, "center")
            d = r.to_dict()
            assert "x" in d
            assert "center" in d

    def test_missing_file(self):
        regions = opencv_processor.extract_visual_regions("/nonexistent.png")
        assert regions == []

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_cap_at_100_regions(self, sample_image_with_shapes):
        regions = opencv_processor.extract_visual_regions(
            sample_image_with_shapes, min_area=1
        )
        assert len(regions) <= 100


class TestRegionComparison:
    """Test region-level comparison for verification."""

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_identical_region(self, sample_image_a, sample_image_identical):
        score = opencv_processor.compare_regions(
            sample_image_a, sample_image_identical, {"x": 10, "y": 10, "w": 50, "h": 50}
        )
        assert score > 0.99

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_different_region(self, sample_image_a, sample_image_b):
        score = opencv_processor.compare_regions(
            sample_image_a, sample_image_b, {"x": 10, "y": 10, "w": 50, "h": 50}
        )
        assert score < 0.5

    def test_missing_file(self, sample_image_a):
        score = opencv_processor.compare_regions(
            sample_image_a, "/nonexistent.png", {"x": 0, "y": 0, "w": 10, "h": 10}
        )
        assert score == 0.0

    @pytest.mark.skipif(
        not opencv_processor.is_available(), reason="OpenCV not installed"
    )
    def test_out_of_bounds_region(self, sample_image_a, sample_image_identical):
        score = opencv_processor.compare_regions(
            sample_image_a,
            sample_image_identical,
            {"x": 9999, "y": 9999, "w": 50, "h": 50},
        )
        assert score == 0.0


class TestGracefulDegradation:
    """Test that all functions degrade gracefully when OpenCV is unavailable."""

    def test_screenshot_diff_no_opencv(self):
        with (
            patch.object(opencv_processor, "_cv2", None),
            patch.object(opencv_processor, "_np", None),
            patch("perception.opencv_processor._ensure_cv2", return_value=False),
        ):
            result = opencv_processor.screenshot_diff("a.png", "b.png")
            assert result.pixel_diff_ratio == 0.0

    def test_preprocess_no_opencv(self):
        with (
            patch.object(opencv_processor, "_cv2", None),
            patch.object(opencv_processor, "_np", None),
            patch("perception.opencv_processor._ensure_cv2", return_value=False),
        ):
            result = opencv_processor.preprocess_for_ocr("a.png")
            assert result is None

    def test_extract_regions_no_opencv(self):
        with (
            patch.object(opencv_processor, "_cv2", None),
            patch.object(opencv_processor, "_np", None),
            patch("perception.opencv_processor._ensure_cv2", return_value=False),
        ):
            result = opencv_processor.extract_visual_regions("a.png")
            assert result == []

    def test_compare_regions_no_opencv(self):
        with (
            patch.object(opencv_processor, "_cv2", None),
            patch.object(opencv_processor, "_np", None),
            patch("perception.opencv_processor._ensure_cv2", return_value=False),
        ):
            result = opencv_processor.compare_regions(
                "a.png", "b.png", {"x": 0, "y": 0, "w": 10, "h": 10}
            )
            assert result == 0.0
