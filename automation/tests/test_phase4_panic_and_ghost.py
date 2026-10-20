"""
Unit tests for Phase 4: Sub-10ms Mouse Panic Killswitch and Ghost Guidance Overlay.
"""

import time

from automation.safety import PanicKillswitch, get_panic_killswitch
from overlay.renderer import OverlayRenderer


def test_panic_killswitch_lifecycle():
    switch = PanicKillswitch(movement_threshold_px=15)
    assert not switch.is_tripped

    switch.arm()
    # No movement simulated
    assert not switch.check()
    assert not switch.is_tripped

    # Manual trip
    switch.trip()
    assert switch.is_tripped
    assert switch.check()

    # Reset
    switch.reset()
    assert not switch.is_tripped
    assert not switch.check()


def test_panic_killswitch_sub_10ms_latency():
    """Verify panic killswitch check executes in << 10.0 ms (target SLA < 0.5 ms)."""
    switch = PanicKillswitch()
    switch.arm()

    iterations = 500
    start = time.perf_counter()
    for _ in range(iterations):
        switch.check()
    duration = time.perf_counter() - start

    avg_ms = (duration / iterations) * 1000.0
    # Win32 GetCursorPos is usually ~0.002ms, well within 10ms SLA
    assert avg_ms < 1.0, f"Average latency {avg_ms:.4f}ms exceeds 1.0ms"


def test_get_panic_killswitch_singleton():
    s1 = get_panic_killswitch()
    s2 = get_panic_killswitch()
    assert s1 is s2


def test_ghost_guidance_renderer():
    renderer = OverlayRenderer()
    assert renderer._ghost_spotlight is None
    assert renderer._ghost_tooltip == ""

    spotlight = {"left": 200, "top": 150, "width": 120, "height": 45}
    tooltip = "Click to confirm payment"
    renderer.set_ghost_spotlight(spotlight, tooltip)

    assert renderer._ghost_spotlight == spotlight
    assert renderer._ghost_tooltip == tooltip

    renderer.clear()
    assert renderer._ghost_spotlight is None
    assert renderer._ghost_tooltip == ""
