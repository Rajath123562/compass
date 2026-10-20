"""
COMPASS Perception Service
Facade over UIA inspector, screen capture, and element filtering.

Provides a unified interface for getting UI snapshots.
Supports configurable polling for Phase 2 diagnostic overlay visualization.
Polling is isolated behind this service and can be stopped cleanly.

Future: replace polling with event/stream-based perception in Phase 3+.
"""

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.app.config import settings
from backend.app.logging_config import logger
from perception import element_filter, screen_capture, uia_inspector
from perception.models import BoundingRect, UIElement, UISnapshot


class PerceptionService:
    """
    Unified perception service.

    Lifecycle:
      start_polling()   → begins background snapshot loop
      stop_polling()    → stops cleanly
      get_snapshot()    → synchronous one-shot snapshot
    """

    def __init__(
        self,
        poll_interval_sec: float = 0.5,
        capture_enabled: bool = False,
        max_depth: int = 3,
        max_elements: int = 200,
    ):
        self.poll_interval_sec = poll_interval_sec
        self.capture_enabled = capture_enabled
        self.max_depth = max_depth
        self.max_elements = max_elements

        self._polling = False
        self._poll_thread: threading.Thread | None = None
        self._last_snapshot: UISnapshot | None = None
        self._snapshot_lock = threading.Lock()
        self._subscribers: list[Callable[[UISnapshot], None]] = []
        self._captures_dir = Path(settings.storage_dir) / "captures"

    def get_snapshot(self, include_capture: bool = False) -> UISnapshot:
        """
        Take a synchronous perception snapshot of the foreground window.

        Returns:
            UISnapshot containing window info, element list, and optional capture.
        """
        snapshot = UISnapshot(timestamp=time.time())

        # Foreground window
        fw_result = uia_inspector.get_foreground_window()
        if not fw_result["success"]:
            snapshot.error = fw_result.get("error", "Foreground window unavailable")
            return snapshot

        from perception.models import WindowInfo

        w = fw_result["window"]
        snapshot.window = WindowInfo(
            hwnd=w["hwnd"],
            process_id=w["process_id"],
            title=w["title"],
            class_name=w["class_name"],
            bounds=BoundingRect.from_dict(w["bounds"]),
            is_visible=w["is_visible"],
            is_minimized=w["is_minimized"],
        )

        # Element tree
        tree_result = uia_inspector.get_element_tree(
            hwnd=w["hwnd"],
            depth=self.max_depth,
            max_elements=self.max_elements,
        )
        if tree_result["success"]:
            snapshot.elements = [
                UIElement(
                    element_id=e.get("element_id", ""),
                    automation_id=e.get("automation_id", ""),
                    runtime_id=e.get("runtime_id", ""),
                    hwnd=e.get("hwnd", 0),
                    process_id=e.get("process_id", 0),
                    window_title=e.get("window_title", ""),
                    control_type=e.get("control_type", ""),
                    control_type_id=e.get("control_type_id", 0),
                    name=e.get("name", ""),
                    text=e.get("text", ""),
                    class_name=e.get("class_name", ""),
                    is_enabled=e.get("is_enabled", True),
                    is_visible=e.get("is_visible", True),
                    is_focused=e.get("is_focused", False),
                    is_offscreen=e.get("is_offscreen", False),
                    bounds=BoundingRect.from_dict(e.get("bounds", {})),
                    parent_control_type=e.get("parent_control_type", ""),
                    depth=e.get("depth", 0),
                    source="uia",
                    confidence=None,
                )
                for e in tree_result["elements"]
            ]
        else:
            snapshot.error = tree_result.get("error")

        # Optional screen capture
        if include_capture and self.capture_enabled:
            cap = screen_capture.capture_foreground_window(
                save_dir=self._captures_dir,
                include_b64=False,
            )
            snapshot.capture = cap

        return snapshot

    def get_filtered_snapshot(
        self,
        filter_mode: str = "all",
        include_capture: bool = False,
    ) -> dict[str, Any]:
        """
        Get a snapshot with optional element filtering.

        Args:
            filter_mode: "all", "interactive", "visible", "editable"
            include_capture: Whether to capture the screen.

        Returns:
            Dict with snapshot data and filter summary.
        """
        snapshot = self.get_snapshot(include_capture=include_capture)
        elements = snapshot.elements

        if filter_mode == "interactive":
            elements = element_filter.filter_interactive(elements)
        elif filter_mode == "visible":
            elements = element_filter.filter_visible(elements)
        elif filter_mode == "editable":
            elements = element_filter.filter_editable(elements)
        elif filter_mode == "ranked":
            elements = element_filter.rank_by_relevance(elements)

        result = snapshot.to_dict()
        result["elements"] = [e.to_dict() for e in elements]
        result["element_count"] = len(elements)
        result["filter_applied"] = filter_mode
        result["summary"] = element_filter.summarize_elements(snapshot.elements)
        return result

    def start_polling(self) -> bool:
        """Start background polling loop. Returns False if already polling."""
        if self._polling:
            return False
        self._polling = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="COMPASS-PerceptionPoller",
            daemon=True,
        )
        self._poll_thread.start()
        logger.info(f"Perception polling started (interval={self.poll_interval_sec}s)")
        return True

    @property
    def is_polling(self) -> bool:
        """Return whether background polling is currently active."""
        return self._polling

    def stop_polling(self) -> bool:
        """Stop the polling loop gracefully. Returns True if stopped, False if was not polling."""
        if not self._polling:
            return False
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None
        logger.info("Perception polling stopped")
        return True

    def _poll_loop(self) -> None:
        """Background polling loop — takes snapshots at configured interval."""
        while self._polling:
            try:
                snapshot = self.get_snapshot(include_capture=False)
                with self._snapshot_lock:
                    self._last_snapshot = snapshot
                for cb in list(self._subscribers):
                    try:
                        cb(snapshot)
                    except Exception:  # noqa: BLE001, S110
                        pass
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Perception poll error: {e}")
            time.sleep(self.poll_interval_sec)

    def get_last_snapshot(self) -> UISnapshot | None:
        """Return the most recent snapshot from polling (None if not polling)."""
        with self._snapshot_lock:
            return self._last_snapshot

    def subscribe(self, callback: Callable[[UISnapshot], None]) -> None:
        """Register a callback to receive each new snapshot during polling."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[UISnapshot], None]) -> None:
        """Unregister a polling callback."""
        self._subscribers = [cb for cb in self._subscribers if cb is not callback]

    def get_status(self) -> dict[str, Any]:
        """Return service health status."""
        uia_status = uia_inspector.get_uia_status()
        cap_caps = screen_capture.get_capture_capabilities()
        return {
            "polling": self._polling,
            "poll_interval_sec": self.poll_interval_sec,
            "capture_enabled": self.capture_enabled,
            "uia": uia_status,
            "screen_capture": cap_caps,
            "last_snapshot_age_sec": (
                round(
                    (time.time() - self._last_snapshot.timestamp.timestamp())
                    if hasattr(self._last_snapshot.timestamp, "timestamp")
                    else (time.time() - self._last_snapshot.timestamp),
                    2,
                )
                if self._last_snapshot
                else None
            ),
        }


# Module-level singleton — shared across backend routes
perception_service = PerceptionService(
    poll_interval_sec=0.5,
    capture_enabled=True,
    max_depth=3,
    max_elements=200,
)

# Re-export Phase 7 multimodal perception service symbols
from perception.multimodal_service import *  # noqa: F401, F403
