"""
COMPASS Phase 7 — Multimodal Perception Configuration & Resource Limits Tests
(Point 4 Pre-Implementation Specification Verification)
"""

from perception.perception_config import (
    MAX_CONCURRENT_OCR_OPS,
    MAX_CONCURRENT_PERCEPTION_OPS,
    MAX_CONCURRENT_VISION_OPS,
    MAX_EVIDENCE_HISTORY,
    MAX_FALLBACK_ATTEMPTS,
    MAX_GPU_VRAM_BUDGET_MB,
    MAX_MODEL_LOAD_SIZE_MB,
    MAX_MODEL_RESIDENCY_SEC,
    MAX_OCR_IMAGE_SIZE,
    MAX_OCR_TIMEOUT_SEC,
    MAX_PERCEPTION_QUEUE_LENGTH,
    MAX_PERCEPTION_RETRIES,
    MAX_PROCESS_RAM_BUDGET_MB,
    MAX_SCREENSHOT_HEIGHT,
    MAX_SCREENSHOT_RETENTION_COUNT,
    MAX_SCREENSHOT_RING_BUFFER_BYTES,
    MAX_SCREENSHOT_WIDTH,
    MAX_SSE_PERCEPTION_EVENT_RATE,
    MAX_TOTAL_PERCEPTION_TIMEOUT_SEC,
    MAX_VISION_TIMEOUT_SEC,
    validate_concurrency,
    validate_image_dimensions,
)


def test_resource_limits_defined_and_positive():
    """Verify all 18 required resource limit constants are strictly positive numbers."""
    assert MAX_SCREENSHOT_WIDTH > 0
    assert MAX_SCREENSHOT_HEIGHT > 0
    assert MAX_OCR_IMAGE_SIZE[0] > 0 and MAX_OCR_IMAGE_SIZE[1] > 0
    assert MAX_CONCURRENT_PERCEPTION_OPS > 0
    assert MAX_CONCURRENT_OCR_OPS > 0
    assert MAX_CONCURRENT_VISION_OPS > 0
    assert MAX_OCR_TIMEOUT_SEC > 0.0
    assert MAX_VISION_TIMEOUT_SEC > 0.0
    assert MAX_TOTAL_PERCEPTION_TIMEOUT_SEC >= MAX_VISION_TIMEOUT_SEC
    assert MAX_EVIDENCE_HISTORY > 0
    assert MAX_SCREENSHOT_RETENTION_COUNT > 0
    assert MAX_SCREENSHOT_RING_BUFFER_BYTES > 0
    assert MAX_SSE_PERCEPTION_EVENT_RATE > 0
    assert MAX_PERCEPTION_QUEUE_LENGTH > 0
    assert MAX_PROCESS_RAM_BUDGET_MB > 0.0
    assert MAX_GPU_VRAM_BUDGET_MB > 0.0
    assert MAX_MODEL_LOAD_SIZE_MB > 0.0
    assert MAX_MODEL_RESIDENCY_SEC > 0.0
    assert MAX_PERCEPTION_RETRIES >= 1
    assert MAX_FALLBACK_ATTEMPTS >= 1


def test_validate_image_dimensions():
    """Test image dimension boundary validation for OCR operations."""
    # Within bounds (1920x1080)
    assert validate_image_dimensions(1920, 1080) is True
    # Exactly max (3840x2160)
    assert (
        validate_image_dimensions(MAX_OCR_IMAGE_SIZE[0], MAX_OCR_IMAGE_SIZE[1]) is True
    )
    # Oversized width
    assert validate_image_dimensions(MAX_OCR_IMAGE_SIZE[0] + 1, 1080) is False
    # Oversized height
    assert validate_image_dimensions(1920, MAX_OCR_IMAGE_SIZE[1] + 1) is False
    # Extreme dimensions
    assert validate_image_dimensions(10000, 10000) is False


def test_validate_concurrency():
    """Test concurrency budget validator."""
    assert validate_concurrency(1) is True
    assert validate_concurrency(MAX_CONCURRENT_PERCEPTION_OPS) is True
    assert validate_concurrency(MAX_CONCURRENT_PERCEPTION_OPS + 1) is False
