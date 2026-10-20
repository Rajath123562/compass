"""
COMPASS Phase 7 — Multimodal Perception Configuration & Resource Limits
(Point 4 Pre-Implementation Specification)

Defines concrete, enforceable, and testable resource budgets across screen capture,
WinRT OCR, vision models, event streaming, memory, and concurrency.
"""

import os

# 1. Screen Capture Dimensions
MAX_SCREENSHOT_WIDTH: int = int(os.getenv("COMPASS_MAX_SCREENSHOT_WIDTH", "1920"))
MAX_SCREENSHOT_HEIGHT: int = int(os.getenv("COMPASS_MAX_SCREENSHOT_HEIGHT", "1080"))

# 2. OCR Image Limits
MAX_OCR_IMAGE_SIZE: tuple[int, int] = (
    int(os.getenv("COMPASS_MAX_OCR_WIDTH", "3840")),
    int(os.getenv("COMPASS_MAX_OCR_HEIGHT", "2160")),
)

# 3. Concurrency Limits
MAX_CONCURRENT_PERCEPTION_OPS: int = int(
    os.getenv("COMPASS_MAX_CONCURRENT_PERCEPTION", "2")
)
MAX_CONCURRENT_OCR_OPS: int = int(os.getenv("COMPASS_MAX_CONCURRENT_OCR", "2"))
MAX_CONCURRENT_VISION_OPS: int = int(os.getenv("COMPASS_MAX_CONCURRENT_VISION", "1"))

# 4. Timeout Budgets (Seconds)
MAX_OCR_TIMEOUT_SEC: float = float(os.getenv("COMPASS_MAX_OCR_TIMEOUT_SEC", "6.0"))
MAX_VISION_TIMEOUT_SEC: float = float(
    os.getenv("COMPASS_MAX_VISION_TIMEOUT_SEC", "10.0")
)
MAX_TOTAL_PERCEPTION_TIMEOUT_SEC: float = float(
    os.getenv("COMPASS_MAX_TOTAL_PERCEPTION_TIMEOUT_SEC", "15.0")
)

# 5. History & Retention Limits
MAX_EVIDENCE_HISTORY: int = int(os.getenv("COMPASS_MAX_EVIDENCE_HISTORY", "100"))
MAX_SCREENSHOT_RETENTION_COUNT: int = int(
    os.getenv("COMPASS_MAX_SCREENSHOT_RETENTION", "10")
)
MAX_SCREENSHOT_RING_BUFFER_BYTES: int = int(
    os.getenv("COMPASS_MAX_RING_BUFFER_BYTES", str(25 * 1024 * 1024))
)  # 25 MB

# 6. SSE & Queue Rate Limits
MAX_SSE_PERCEPTION_EVENT_RATE: int = int(
    os.getenv("COMPASS_MAX_SSE_EVENT_RATE", "20")
)  # events / sec
MAX_PERCEPTION_QUEUE_LENGTH: int = int(os.getenv("COMPASS_MAX_PERCEPTION_QUEUE", "10"))

# 7. Hardware & Memory Budgets (MB)
MAX_PROCESS_RAM_BUDGET_MB: float = float(
    os.getenv("COMPASS_MAX_RAM_BUDGET_MB", "250.0")
)
MAX_GPU_VRAM_BUDGET_MB: float = float(os.getenv("COMPASS_MAX_VRAM_BUDGET_MB", "1000.0"))

# 8. Model Lifecycle & Residency
MAX_MODEL_LOAD_SIZE_MB: float = float(
    os.getenv("COMPASS_MAX_MODEL_LOAD_SIZE_MB", "500.0")
)
MAX_MODEL_RESIDENCY_SEC: float = float(
    os.getenv("COMPASS_MAX_MODEL_RESIDENCY_SEC", "300.0")
)

# 9. Retries & Recovery Limits
MAX_PERCEPTION_RETRIES: int = int(os.getenv("COMPASS_MAX_PERCEPTION_RETRIES", "2"))
MAX_FALLBACK_ATTEMPTS: int = int(os.getenv("COMPASS_MAX_FALLBACK_ATTEMPTS", "2"))


def validate_image_dimensions(width: int, height: int) -> bool:
    """Validate that image dimensions do not exceed maximum OCR limits."""
    return width <= MAX_OCR_IMAGE_SIZE[0] and height <= MAX_OCR_IMAGE_SIZE[1]


def validate_concurrency(active_ops: int) -> bool:
    """Ensure active perception operations remain within concurrency budget."""
    return active_ops <= MAX_CONCURRENT_PERCEPTION_OPS
