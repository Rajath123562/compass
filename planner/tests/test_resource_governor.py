"""
Unit tests for Resource Governor & Ring Buffer (Phase 4, Addendum §3, Directive §26).
"""

from backend.app.models import TaskState
from planner.resource_governor import ResourceGovernor, ScreenshotRingBuffer


def test_screenshot_ring_buffer_bounded_capacity():
    """Verify screenshot ring buffer never exceeds max frames (evicts oldest)."""
    buf = ScreenshotRingBuffer(max_frames=5)
    for i in range(10):
        buf.add_frame(f"frame_{i}")

    assert buf.count() == 5
    latest = buf.get_latest()
    assert latest["data"] == "frame_9"


def test_resource_governor_measurement_breakdown():
    """Verify distinct separation between process RSS, system RAM, and GPU."""
    gov = ResourceGovernor(ring_buffer_size=5)
    snapshot = gov.measure_resources()

    assert snapshot.compass_backend_rss_mb > 0.0
    assert snapshot.compass_total_rss_mb >= snapshot.compass_backend_rss_mb
    assert snapshot.system_ram_total_mb > 1000.0  # At least 1GB
    assert snapshot.budget_target_mb == 200.0


def test_adaptive_observation_interval():
    gov = ResourceGovernor()
    assert gov.get_adaptive_observation_interval_ms(TaskState.IDLE) == 1000.0
    assert (
        gov.get_adaptive_observation_interval_ms(TaskState.WAITING_CONFIRMATION)
        == 1000.0
    )
    assert gov.get_adaptive_observation_interval_ms(TaskState.PLANNING) == 500.0
    assert gov.get_adaptive_observation_interval_ms(TaskState.EXECUTING) == 150.0
    assert gov.get_adaptive_observation_interval_ms(TaskState.VERIFYING) == 150.0
