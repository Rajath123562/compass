"""
COMPASS — OpenCV Visual Processor
Integrates OpenCV (open-source, Apache 2.0) into the COMPASS perception layer.

Provides:
  - screenshot_diff()          -> structural + pixel difference metrics
  - detect_visual_changes()    -> region-level change detection
  - preprocess_for_ocr()       -> image preprocessing to improve OCR accuracy
  - extract_visual_regions()   -> contour-based interactive region extraction
  - compare_regions()          -> SSIM-based region comparison for verification

Does NOT replace existing Pillow-based temporal_comparator.
Does NOT execute any actions.
All outputs feed into COMPASS perception fusion and validation layers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import to avoid startup crash if OpenCV is missing
_cv2 = None
_np = None


def _ensure_cv2():
    """Lazy-load OpenCV and numpy. Returns True if available."""
    global _cv2, _np
    if _cv2 is not None:
        return True
    try:
        import cv2
        import numpy as np

        _cv2 = cv2
        _np = np
        logger.info(f"OpenCV {cv2.__version__} loaded successfully")
        return True
    except ImportError:
        logger.warning("OpenCV not available — visual processing degraded")
        return False


def is_available() -> bool:
    """Check if OpenCV is installed and importable."""
    return _ensure_cv2()


@dataclass
class VisualDiffResult:
    """Result from comparing two screenshots."""

    pixel_diff_ratio: float = 0.0  # 0.0 = identical, 1.0 = completely different
    structural_similarity: float = (
        1.0  # SSIM: 1.0 = identical, 0.0 = completely different
    )
    changed_region_count: int = 0
    changed_regions: list[dict[str, int]] = field(
        default_factory=list
    )  # list of {x, y, w, h}
    total_changed_pixels: int = 0
    computation_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pixel_diff_ratio": round(self.pixel_diff_ratio, 4),
            "structural_similarity": round(self.structural_similarity, 4),
            "changed_region_count": self.changed_region_count,
            "changed_regions": self.changed_regions[:10],  # Cap at 10 for safety
            "total_changed_pixels": self.total_changed_pixels,
            "computation_ms": round(self.computation_ms, 2),
        }


@dataclass
class VisualRegion:
    """A detected interactive region in a screenshot."""

    x: int
    y: int
    width: int
    height: int
    area: int
    aspect_ratio: float
    is_button_like: bool = False
    center: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "area": self.area,
            "aspect_ratio": round(self.aspect_ratio, 2),
            "is_button_like": self.is_button_like,
            "center": list(self.center),
        }


def screenshot_diff(
    img_path_a: str,
    img_path_b: str,
    change_threshold: int = 30,
    min_region_area: int = 100,
) -> VisualDiffResult:
    """
    Compare two screenshots using OpenCV.
    Returns pixel diff ratio, SSIM, and bounding boxes of changed regions.
    Falls back to empty result if OpenCV is unavailable.
    """
    result = VisualDiffResult()
    start = time.time()

    if not _ensure_cv2():
        return result

    p_a, p_b = Path(img_path_a), Path(img_path_b)
    if not p_a.exists() or not p_b.exists():
        return result

    try:
        img_a = _cv2.imread(str(p_a))
        img_b = _cv2.imread(str(p_b))
        if img_a is None or img_b is None:
            return result

        # Resize to match if needed
        if img_a.shape != img_b.shape:
            img_b = _cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))

        # Convert to grayscale
        gray_a = _cv2.cvtColor(img_a, _cv2.COLOR_BGR2GRAY)
        gray_b = _cv2.cvtColor(img_b, _cv2.COLOR_BGR2GRAY)

        # Pixel difference
        diff = _cv2.absdiff(gray_a, gray_b)
        total_pixels = diff.shape[0] * diff.shape[1]
        changed_pixels = int(_np.count_nonzero(diff > change_threshold))
        result.pixel_diff_ratio = changed_pixels / max(total_pixels, 1)
        result.total_changed_pixels = changed_pixels

        # Structural Similarity (simplified SSIM using mean/std)
        mean_a, std_a = _cv2.meanStdDev(gray_a)
        mean_b, std_b = _cv2.meanStdDev(gray_b)
        C1 = 6.5025  # (0.01 * 255)^2
        C2 = 58.5225  # (0.03 * 255)^2
        mean_a_val = float(mean_a[0][0])
        mean_b_val = float(mean_b[0][0])
        std_a_val = float(std_a[0][0])
        std_b_val = float(std_b[0][0])
        cov = float(
            _np.mean(
                (gray_a.astype(float) - mean_a_val)
                * (gray_b.astype(float) - mean_b_val)
            )
        )
        ssim = ((2 * mean_a_val * mean_b_val + C1) * (2 * cov + C2)) / (
            (mean_a_val**2 + mean_b_val**2 + C1) * (std_a_val**2 + std_b_val**2 + C2)
        )
        result.structural_similarity = max(0.0, min(1.0, ssim))

        # Find changed regions via contours
        _, thresh = _cv2.threshold(diff, change_threshold, 255, _cv2.THRESH_BINARY)
        # Dilate to merge nearby changes
        kernel = _cv2.getStructuringElement(_cv2.MORPH_RECT, (5, 5))
        dilated = _cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = _cv2.findContours(
            dilated, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            x, y, w, h = _cv2.boundingRect(cnt)
            area = w * h
            if area >= min_region_area:
                result.changed_regions.append({"x": x, "y": y, "w": w, "h": h})

        result.changed_region_count = len(result.changed_regions)
        result.computation_ms = (time.time() - start) * 1000

    except Exception as e:  # noqa: BLE001
        logger.error(f"OpenCV screenshot_diff failed: {e}")

    return result


def preprocess_for_ocr(
    img_path: str,
    output_path: str | None = None,
    denoise: bool = True,
    binarize: bool = True,
    scale_factor: float = 2.0,
) -> str | None:
    """
    Preprocess a screenshot image to improve OCR accuracy.
    Returns path to the preprocessed image, or None on failure.
    Does not modify the original image.
    """
    if not _ensure_cv2():
        return None

    p = Path(img_path)
    if not p.exists():
        return None

    try:
        img = _cv2.imread(str(p))
        if img is None:
            return None

        # Convert to grayscale
        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)

        # Upscale for small text
        if scale_factor > 1.0:
            h, w = gray.shape
            gray = _cv2.resize(
                gray,
                (int(w * scale_factor), int(h * scale_factor)),
                interpolation=_cv2.INTER_CUBIC,
            )

        # Denoise
        if denoise:
            gray = _cv2.fastNlMeansDenoising(gray, h=10)

        # Adaptive binarization
        if binarize:
            gray = _cv2.adaptiveThreshold(
                gray, 255, _cv2.ADAPTIVE_THRESH_GAUSSIAN_C, _cv2.THRESH_BINARY, 11, 2
            )

        # Write output
        if output_path is None:
            output_path = str(p.parent / f"{p.stem}_ocr_preprocessed{p.suffix}")

        _cv2.imwrite(output_path, gray)
        return output_path

    except Exception as e:  # noqa: BLE001
        logger.error(f"OpenCV preprocess_for_ocr failed: {e}")
        return None


def extract_visual_regions(
    img_path: str,
    min_area: int = 200,
    max_area: int = 500000,
    button_aspect_range: tuple[float, float] = (1.5, 8.0),
) -> list[VisualRegion]:
    """
    Extract potential interactive regions (buttons, fields, etc.) from a screenshot
    using edge detection and contour analysis.
    Returns list of VisualRegion, sorted by area descending.
    """
    if not _ensure_cv2():
        return []

    p = Path(img_path)
    if not p.exists():
        return []

    try:
        img = _cv2.imread(str(p))
        if img is None:
            return []

        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
        blurred = _cv2.GaussianBlur(gray, (5, 5), 0)
        edges = _cv2.Canny(blurred, 50, 150)

        # Dilate edges to close gaps
        kernel = _cv2.getStructuringElement(_cv2.MORPH_RECT, (3, 3))
        dilated = _cv2.dilate(edges, kernel, iterations=2)

        contours, _ = _cv2.findContours(
            dilated, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE
        )

        regions: list[VisualRegion] = []
        for cnt in contours:
            x, y, w, h = _cv2.boundingRect(cnt)
            area = w * h
            if area < min_area or area > max_area:
                continue

            aspect = w / max(h, 1)
            is_button = (
                button_aspect_range[0] <= aspect <= button_aspect_range[1]
                and 20 <= h <= 80
            )
            regions.append(
                VisualRegion(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    area=area,
                    aspect_ratio=aspect,
                    is_button_like=is_button,
                    center=(x + w // 2, y + h // 2),
                )
            )

        regions.sort(key=lambda r: r.area, reverse=True)
        return regions[:100]  # Cap at 100 regions

    except Exception as e:  # noqa: BLE001
        logger.error(f"OpenCV extract_visual_regions failed: {e}")
        return []


def compare_regions(
    img_path_a: str,
    img_path_b: str,
    region: dict[str, int],
) -> float:
    """
    Compare a specific region between two screenshots using SSIM.
    Returns similarity score: 1.0 = identical, 0.0 = completely different.
    Useful for verification (did a button change state after clicking?).
    """
    if not _ensure_cv2():
        return 0.0

    try:
        img_a = _cv2.imread(img_path_a)
        img_b = _cv2.imread(img_path_b)
        if img_a is None or img_b is None:
            return 0.0

        x, y = region.get("x", 0), region.get("y", 0)
        w, h = region.get("w", 50), region.get("h", 50)

        # Bounds check
        h_a, w_a = img_a.shape[:2]
        x2 = min(x + w, w_a)
        y2 = min(y + h, h_a)
        if x >= w_a or y >= h_a or x2 <= x or y2 <= y:
            return 0.0

        crop_a = _cv2.cvtColor(img_a[y:y2, x:x2], _cv2.COLOR_BGR2GRAY)
        crop_b = _cv2.cvtColor(img_b[y:y2, x:x2], _cv2.COLOR_BGR2GRAY)

        if crop_a.shape != crop_b.shape:
            crop_b = _cv2.resize(crop_b, (crop_a.shape[1], crop_a.shape[0]))

        # Compute simplified SSIM on region
        mean_a = float(_np.mean(crop_a))
        mean_b = float(_np.mean(crop_b))
        std_a = float(_np.std(crop_a))
        std_b = float(_np.std(crop_b))
        cov = float(
            _np.mean((crop_a.astype(float) - mean_a) * (crop_b.astype(float) - mean_b))
        )

        C1, C2 = 6.5025, 58.5225
        ssim = ((2 * mean_a * mean_b + C1) * (2 * cov + C2)) / (
            (mean_a**2 + mean_b**2 + C1) * (std_a**2 + std_b**2 + C2)
        )
        return max(0.0, min(1.0, ssim))

    except Exception as e:  # noqa: BLE001
        logger.error(f"OpenCV compare_regions failed: {e}")
        return 0.0
