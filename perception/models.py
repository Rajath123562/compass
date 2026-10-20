from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CoordinateSpace(str, Enum):
    LOGICAL = "LOGICAL"
    PHYSICAL = "PHYSICAL"
    SCREEN_PHYSICAL = "screen_physical"
    SCREEN_LOGICAL = "screen_logical"
    SCREEN_LOGICAL_DPI = "screen_logical_dpi"
    WINDOW_RELATIVE = "window_relative"
    NORMALIZED = "normalized"
    NORMALIZED_01 = "normalized_01"


class CoordinateBounds(BaseModel):
    """Represents a bounding box in a specific coordinate space."""

    left: int
    top: int
    right: int
    bottom: int
    coordinate_space: CoordinateSpace = Field(default=CoordinateSpace.LOGICAL)
    monitor_dpi: int | None = Field(
        default=None, description="DPI of the monitor where this bounds exists"
    )

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class TemporalDelta(BaseModel):
    """Represents a temporal change between two states (e.g. before/after action)."""

    pre_hash: str | None = Field(
        default=None, description="Hash or identifier of the pre-action image"
    )
    post_hash: str | None = Field(
        default=None, description="Hash or identifier of the post-action image"
    )
    diff_ratio: float = Field(
        default=0.0, description="Percentage/ratio of pixels changed"
    )
    transition_type: str | None = Field(
        default=None, description="Classified transition type e.g., TARGET_APPEARED"
    )


class OcrElement(BaseModel):
    """An element recognized by the OCR engine."""

    text: str
    bounds: CoordinateBounds
    confidence: float = Field(default=1.0)


class UiaElement(BaseModel):
    """An element recognized by the UI Automation tree."""

    name: str
    control_type: str
    runtime_id: str | None = None
    bounds: CoordinateBounds | None = None
    automation_id: str | None = None
    confidence: float = Field(default=1.0)


class FusedCluster(BaseModel):
    """A spatial cluster linking an OCR element and a UIA element."""

    bounds: CoordinateBounds
    ocr_element: OcrElement | None = None
    uia_element: UiaElement | None = None
    consistency_state: str = Field(
        default="UNKNOWN", description="CONSISTENT, UIA_ONLY, OCR_ONLY, CONFLICT"
    )
    confidence: float = Field(default=1.0)
    cluster_id: str | None = None
    primary_uia: UiaElement | None = None
    associated_ocr: list[OcrElement] = Field(default_factory=list)


class MultimodalEvidence(BaseModel):
    """Canonical model for a snapshot of perception evidence."""

    id: str = Field(..., description="Unique identifier for this evidence snapshot")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    hwnd: int | None = Field(default=None, description="Target window handle")
    window_title: str | None = Field(default=None, description="Target window title")

    uia_elements: list[UiaElement] = Field(default_factory=list)
    ocr_elements: list[OcrElement] = Field(default_factory=list)
    fused_clusters: list[FusedCluster] = Field(default_factory=list)


# --- Legacy Aliases for Phase 1-6 Tests ---
import uuid


class BoundingRect(CoordinateBounds):
    def __init__(
        self, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0, **kwargs
    ):
        # Allow positional initialization for legacy tests
        if not kwargs.get("coordinate_space"):
            kwargs["left"] = left
            kwargs["top"] = top
            kwargs["right"] = right
            kwargs["bottom"] = bottom
        super().__init__(**kwargs)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @classmethod
    def from_ltwh(cls, left: int, top: int, width: int, height: int) -> "BoundingRect":
        return cls(left=left, top=top, right=left + width, bottom=top + height)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "BoundingRect":
        if not d or not isinstance(d, dict):
            return cls()
        if "width" in d and "right" not in d:
            left = d.get("left", 0)
            top = d.get("top", 0)
            return cls.from_ltwh(left, top, d.get("width", 0), d.get("height", 0))
        return cls(
            left=d.get("left", 0),
            top=d.get("top", 0),
            right=d.get("right", 0),
            bottom=d.get("bottom", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump()
        d["width"] = self.width
        d["height"] = self.height
        return d


class WindowInfo(BaseModel):
    title: str = ""
    hwnd: int = 0
    handle: int = 0
    process_id: int = 0
    class_name: str = ""
    bounds: BoundingRect | None = None
    is_visible: bool = True
    is_minimized: bool = False

    def model_post_init(self, __context: Any) -> None:
        if self.hwnd and not self.handle:
            self.handle = self.hwnd
        elif self.handle and not self.hwnd:
            self.hwnd = self.handle

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump()
        if not d.get("hwnd") and d.get("handle"):
            d["hwnd"] = d["handle"]
        if not d.get("handle") and d.get("hwnd"):
            d["handle"] = d["hwnd"]
        return d


class UIElement(UiaElement):
    element_id: str = ""
    is_enabled: bool = True
    is_visible: bool = True
    is_offscreen: bool = False
    is_focused: bool = False
    text: str = ""
    source: str = "uia"
    confidence: float | None = None
    children: list["UIElement"] = Field(default_factory=list)
    hwnd: int = 0
    process_id: int = 0
    window_title: str = ""
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class UISnapshot(MultimodalEvidence):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this evidence snapshot",
    )
    elements: list[UIElement] = Field(default_factory=list)
    focused_element: UIElement | None = None
    window_info: WindowInfo | None = None
    window: WindowInfo | None = None
    error: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.window and not self.window_info:
            self.window_info = self.window
        elif self.window_info and not self.window:
            self.window = self.window_info

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump()
        if not d.get("window") and d.get("window_info"):
            d["window"] = d["window_info"]
        if not d.get("window_info") and d.get("window"):
            d["window_info"] = d["window"]
        return d


class CaptureResult(BaseModel):
    filepath: str | None = None
    timestamp: float = 0.0
    success: bool = True
    png_path: str | None = None
    width: int = 0
    height: int = 0
    format: str = "BGRA"
    data_b64: str | None = None
    capture_region: Any = None
    latency_ms: float = 0.0
    error: str | None = None
