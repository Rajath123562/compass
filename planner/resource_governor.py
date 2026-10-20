"""
COMPASS Phase 4 — Measured Resource Governor & Ring Buffer
Maintains bounded screenshot ring buffer (max 5 frames).
Accurately measures and distinguishes COMPASS process RSS from System RAM and GPU VRAM.
Enforces adaptive perception frequency based on execution state.
"""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Any

import psutil
from pydantic import BaseModel

from backend.app.models import TaskState


class ResourceSnapshot(BaseModel):
    """Accurate, measured hardware and process telemetry."""

    compass_backend_rss_mb: float
    compass_overlay_rss_mb: float
    compass_total_rss_mb: float
    system_ram_total_mb: float
    system_ram_used_mb: float
    system_ram_percent: float
    gpu_vram_total_mb: float | None = None
    gpu_vram_used_mb: float | None = None
    cpu_percent: float
    screenshot_buffer_count: int
    is_within_budget: bool
    budget_target_mb: float = 200.0


class ScreenshotRingBuffer:
    """
    Fixed-capacity ring buffer for desktop screenshot frames.
    Strictly prevents runaway memory consumption by evicting oldest frames.
    """

    def __init__(self, max_frames: int = 5):
        self._max_frames = max_frames
        self._buffer: deque = deque(maxlen=max_frames)

    def add_frame(self, frame_data: Any, timestamp: float | None = None) -> None:
        self._buffer.append({"data": frame_data, "timestamp": timestamp or time.time()})

    def get_latest(self) -> dict[str, Any] | None:
        if not self._buffer:
            return None
        return self._buffer[-1]

    def count(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()


MAX_ACTIONS_PER_TASK = 50
MAX_PLAN_LENGTH = 20
MAX_RECOVERY_ATTEMPTS = 5
MAX_TIMELINE_ENTRIES = 500
MAX_SCREENSHOT_RESOLUTION = (1920, 1080)
SCREENSHOT_RATE_LIMIT_HZ = 2.0  # Max 2 screenshots/sec

# Phase 8 Autonomous Workflow Resource Bounds
MAX_ACTIVE_WORKFLOWS = 3
MAX_NODES_PER_WORKFLOW = 30
MAX_CONCURRENT_NODES = 2
MAX_WORKFLOW_DURATION_S = 600.0
MAX_WORKFLOW_RETRIES = 10


class ResourceGovernor:
    """
    Hardware-aware resource governor.
    Monitors process memory, system RAM, VRAM, and adaptively governs observation intervals.
    Enforces strict operational action and timeline bounds (§16).
    """

    def __init__(self, ring_buffer_size: int = 5, cache_ttl_s: float = 0.25):
        self.ring_buffer = ScreenshotRingBuffer(max_frames=ring_buffer_size)
        self._process = psutil.Process(os.getpid())
        self._last_snapshot: ResourceSnapshot | None = None
        self._last_snapshot_time: float = 0.0
        self._cache_ttl_s = cache_ttl_s

    def check_action_budget(self, action_count: int) -> tuple[bool, str]:
        """Check if action count exceeds task budget."""
        if action_count > MAX_ACTIONS_PER_TASK:
            return (
                False,
                f"Action budget exhausted: executed {action_count} actions (maximum {MAX_ACTIONS_PER_TASK}).",
            )
        return True, "Within action budget."

    def check_timeline_budget(self, timeline_count: int) -> tuple[bool, str]:
        """Check if timeline entries exceed budget."""
        if timeline_count > MAX_TIMELINE_ENTRIES:
            return (
                False,
                f"Timeline budget exhausted: {timeline_count} entries (maximum {MAX_TIMELINE_ENTRIES}).",
            )
        return True, "Within timeline budget."

    def check_plan_length(self, step_count: int) -> tuple[bool, str]:
        """Check if plan exceeds max allowed steps."""
        if step_count > MAX_PLAN_LENGTH:
            return (
                False,
                f"Plan exceeds maximum allowed steps: {step_count} > {MAX_PLAN_LENGTH}.",
            )
        return True, "Plan length within budget."

    def check_workflow_node_budget(self, node_count: int) -> tuple[bool, str]:
        """Check if workflow node count is within limits."""
        if node_count > MAX_NODES_PER_WORKFLOW:
            return (
                False,
                f"Workflow node count {node_count} exceeds maximum allowed {MAX_NODES_PER_WORKFLOW}.",
            )
        return True, "Workflow node count within budget."

    def check_active_workflows_budget(self, active_count: int) -> tuple[bool, str]:
        """Check if active workflow count is within limits."""
        if active_count >= MAX_ACTIVE_WORKFLOWS:
            return (
                False,
                f"Active workflow count {active_count} reached maximum allowed {MAX_ACTIVE_WORKFLOWS}.",
            )
        return True, "Active workflow count within budget."

    def check_concurrent_nodes_budget(self, concurrent_count: int) -> tuple[bool, str]:
        """Check if concurrent nodes executing is within limits."""
        if concurrent_count >= MAX_CONCURRENT_NODES:
            return (
                False,
                f"Concurrent nodes {concurrent_count} reached maximum allowed {MAX_CONCURRENT_NODES}.",
            )
        return True, "Concurrent nodes within budget."

    def check_workflow_duration(
        self, start_time: float, max_duration_s: float | None = None
    ) -> tuple[bool, str]:
        """Check if workflow execution elapsed time exceeds deadline."""
        limit = max_duration_s or MAX_WORKFLOW_DURATION_S
        elapsed = time.time() - start_time
        if elapsed > limit:
            return (
                False,
                f"Workflow timed out: {elapsed:.1f}s exceeded limit of {limit:.1f}s.",
            )
        return True, f"Elapsed {elapsed:.1f}s within limit of {limit:.1f}s."

    def check_workflow_retries(
        self, retry_count: int, max_retries: int = MAX_WORKFLOW_RETRIES
    ) -> tuple[bool, str]:
        """Check if cumulative workflow retries are within budget."""
        if retry_count >= max_retries:
            return (
                False,
                f"Retry budget exhausted: {retry_count} retries reached limit of {max_retries}.",
            )
        return True, f"Retry count {retry_count} within budget {max_retries}."

    def record_frame(self, frame_data: Any) -> None:
        """Store frame in bounded ring buffer."""
        self.ring_buffer.add_frame(frame_data)

    def clear_ring_buffer(self) -> None:
        """Clear all frames from ring buffer."""
        self.ring_buffer.clear()

    def get_adaptive_observation_interval_ms(self, state: TaskState) -> float:
        """
        Adaptive observation interval:
          - IDLE / WAITING: slow polling (1000ms) to conserve CPU/RAM
          - PLANNING / DECIDING: moderate (500ms)
          - EXECUTING / VERIFYING: responsive (150ms)
        """
        if state in [
            TaskState.IDLE,
            TaskState.WAITING_FOR_USER,
            TaskState.WAITING_CONFIRMATION,
            TaskState.BLOCKED,
        ]:
            return 1000.0
        elif state in [
            TaskState.PLANNING,
            TaskState.DECIDING,
            TaskState.REPLANNING,
            TaskState.RECOVERING,
        ]:
            return 500.0
        elif state in [TaskState.EXECUTING, TaskState.ACTING, TaskState.VERIFYING]:
            return 150.0
        return 300.0

    def measure_resources(self) -> ResourceSnapshot:
        """
        Produce a verified, measured breakdown of memory and hardware usage.
        Distinguishes COMPASS process RSS from total system RAM and GPU VRAM.
        Caches snapshot for 250ms to prevent expensive full-OS process scans in burst loops.
        """
        now = time.time()
        if (
            self._last_snapshot is not None
            and (now - self._last_snapshot_time) < self._cache_ttl_s
        ):
            return self._last_snapshot

        # 1. COMPASS Backend Process Memory
        try:
            backend_rss_bytes = self._process.memory_info().rss
            backend_rss_mb = round(backend_rss_bytes / (1024 * 1024), 2)
            cpu_pct = round(self._process.cpu_percent(interval=0.0), 1)
        except Exception:  # noqa: BLE001
            backend_rss_mb = 0.0
            cpu_pct = 0.0

        # 2. PySide6 Overlay Process Memory (if running)
        overlay_rss_mb = 0.0
        try:
            for p in psutil.process_iter(["name", "cmdline", "memory_info"]):
                try:
                    cmd = " ".join(p.info.get("cmdline") or [])
                    if (
                        "overlay" in cmd
                        and "python" in p.info.get("name", "").lower()
                        and p.pid != self._process.pid
                    ):
                        overlay_rss_mb += round(
                            p.info["memory_info"].rss / (1024 * 1024), 2
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:  # noqa: BLE001, S110
            pass

        total_compass_rss = round(backend_rss_mb + overlay_rss_mb, 2)

        # 3. Whole System RAM
        try:
            sys_mem = psutil.virtual_memory()
            sys_total_mb = round(sys_mem.total / (1024 * 1024), 2)
            sys_used_mb = round(sys_mem.used / (1024 * 1024), 2)
            sys_pct = sys_mem.percent
        except Exception:  # noqa: BLE001
            sys_total_mb = 0.0
            sys_used_mb = 0.0
            sys_pct = 0.0

        # 4. GPU / VRAM telemetry (Target machine: RTX 2050 4GB)
        gpu_total_mb = None
        gpu_used_mb = None
        try:
            # Try reading via nvidia-smi if available
            import subprocess

            res = subprocess.run(  # noqa: PLW1510
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used",
                    "--format=csv,nounits,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split("\n")[0].split(",")
                if len(parts) >= 2:
                    gpu_total_mb = float(parts[0].strip())
                    gpu_used_mb = float(parts[1].strip())
        except Exception:  # noqa: BLE001, S110
            pass

        is_within_budget = total_compass_rss <= 200.0

        snap = ResourceSnapshot(
            compass_backend_rss_mb=backend_rss_mb,
            compass_overlay_rss_mb=overlay_rss_mb,
            compass_total_rss_mb=total_compass_rss,
            system_ram_total_mb=sys_total_mb,
            system_ram_used_mb=sys_used_mb,
            system_ram_percent=sys_pct,
            gpu_vram_total_mb=gpu_total_mb,
            gpu_vram_used_mb=gpu_used_mb,
            cpu_percent=cpu_pct,
            screenshot_buffer_count=self.ring_buffer.count(),
            is_within_budget=is_within_budget,
            budget_target_mb=200.0,
        )
        self._last_snapshot = snap
        self._last_snapshot_time = now
        return snap


resource_governor = ResourceGovernor()
