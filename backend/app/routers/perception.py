"""
COMPASS Perception API Router
Endpoints for foreground window discovery, element tree, capture, and element search.

Routes:
  GET  /api/perception/foreground          → foreground window metadata
  GET  /api/perception/elements            → element tree (filter param supported)
  POST /api/perception/capture             → screen region / foreground capture
  POST /api/perception/find               → find element by name or type
  GET  /api/perception/status             → UIA + capture subsystem status
"""

import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from perception import element_filter, screen_capture, uia_inspector
from perception.service import perception_service

router = APIRouter(prefix="/api/perception", tags=["perception"])


# ─── Request / Response Models ─────────────────────────────────────────────────


class CaptureRequest(BaseModel):
    mode: str = Field(
        default="foreground",
        description="Capture mode: 'foreground', 'region', 'fullscreen'",
    )
    x: int | None = Field(
        default=None, description="Region left (for mode='region')"
    )
    y: int | None = Field(default=None, description="Region top (for mode='region')")
    width: int | None = Field(default=None, description="Region width")
    height: int | None = Field(default=None, description="Region height")
    include_b64: bool = Field(
        default=False, description="Include base64 image data in response"
    )
    save_png: bool = Field(
        default=True, description="Save PNG to storage/captures/ if Pillow available"
    )


class FindRequest(BaseModel):
    hwnd: int | None = Field(
        default=None, description="Target HWND (default: foreground)"
    )
    name: str | None = Field(
        default=None, description="Element name to search (substring match)"
    )
    control_type: str | None = Field(
        default=None, description="Control type to filter by"
    )
    exact_name: bool = Field(
        default=False, description="Exact name match instead of substring"
    )


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("/foreground")
async def get_foreground_window():
    """
    Return metadata for the current foreground window.
    Includes HWND, title, class, PID, bounding rect, and minimized state.
    """
    result = uia_inspector.get_foreground_window()
    if not result["success"]:
        return JSONResponse(
            status_code=503,
            content={
                "error": True,
                "detail": result.get("error", "Foreground window unavailable"),
            },
        )
    return result


@router.get("/elements")
async def get_elements(
    hwnd: int | None = Query(
        default=None, description="Target HWND (default: foreground)"
    ),
    filter: str | None = Query(
        default="all",
        description="Filter mode: 'all', 'interactive', 'visible', 'editable', 'ranked'",
    ),
    depth: int = Query(default=3, ge=1, le=6, description="UIA traversal depth (1-6)"),
    max_elements: int = Query(
        default=200, ge=1, le=500, description="Max elements returned"
    ),
):
    """
    Return the UI element tree for the specified window.
    Applies optional element filtering.
    """
    # Resolve HWND
    if hwnd is None:
        fw = uia_inspector.get_foreground_window()
        if not fw["success"]:
            return JSONResponse(
                status_code=503,
                content={"error": True, "detail": "Cannot determine foreground window"},
            )
        hwnd = fw["window"]["hwnd"]

    result = uia_inspector.get_element_tree(
        hwnd, depth=depth, max_elements=max_elements
    )
    if not result["success"]:
        return JSONResponse(
            status_code=503,
            content={
                "error": True,
                "detail": result.get("error", "Element tree unavailable"),
            },
        )

    elements_raw = result["elements"]

    # Apply filter using parsed UIElement objects
    from perception.models import BoundingRect, UIElement

    elements = [
        UIElement(
            element_id=e.get("element_id", ""),
            automation_id=e.get("automation_id", ""),
            runtime_id=e.get("runtime_id", ""),
            hwnd=e.get("hwnd", 0),
            process_id=e.get("process_id", 0),
            window_title=e.get("window_title", ""),
            control_type=e.get("control_type", ""),
            name=e.get("name", ""),
            text=e.get("text", ""),
            is_enabled=e.get("is_enabled", True),
            is_visible=e.get("is_visible", True),
            is_focused=e.get("is_focused", False),
            is_offscreen=e.get("is_offscreen", False),
            bounds=BoundingRect(
                left=e.get("bounds", {}).get("left", 0),
                top=e.get("bounds", {}).get("top", 0),
                right=e.get("bounds", {}).get("right", 0),
                bottom=e.get("bounds", {}).get("bottom", 0)
            ) if e.get("bounds") else None,
            depth=e.get("depth", 0),
            source="uia",
        )
        for e in elements_raw
    ]

    filter_mode = (filter or "all").lower()
    if filter_mode == "interactive":
        elements = element_filter.filter_interactive(elements)
    elif filter_mode == "visible":
        elements = element_filter.filter_visible(elements)
    elif filter_mode == "editable":
        elements = element_filter.filter_editable(elements)
    elif filter_mode == "ranked":
        elements = element_filter.rank_by_relevance(elements)

    summary = element_filter.summarize_elements(elements)

    return {
        "success": True,
        "hwnd": hwnd,
        "window_title": result.get("window_title", ""),
        "filter_applied": filter_mode,
        "element_count": len(elements),
        "elements": [e.to_dict() for e in elements],
        "summary": summary,
        "timestamp": time.time(),
    }


@router.post("/capture")
async def capture_screen(request: CaptureRequest):
    """
    Capture the screen (foreground window, region, or full screen).
    Returns capture metadata and optional base64 image data.
    """
    from pathlib import Path

    from backend.app.config import settings

    save_dir = Path(settings.storage_dir) / "captures" if request.save_png else None
    mode = request.mode.lower()

    if mode == "foreground":
        result = screen_capture.capture_foreground_window(
            save_dir=save_dir,
            include_b64=request.include_b64,
        )
    elif mode == "region":
        if None in (request.x, request.y, request.width, request.height):
            raise HTTPException(
                status_code=422,
                detail="Region capture requires x, y, width, height parameters",
            )
        if request.width <= 0 or request.height <= 0:
            raise HTTPException(
                status_code=422, detail="Width and height must be positive"
            )
        result = screen_capture.capture_region(
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
            save_dir=save_dir,
            include_b64=request.include_b64,
        )
    elif mode == "fullscreen":
        result = screen_capture.capture_full_screen(
            save_dir=save_dir,
            include_b64=request.include_b64,
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown capture mode '{mode}'. Expected: foreground, region, fullscreen",
        )

    if not result.success:
        return JSONResponse(
            status_code=503,
            content={"error": True, "detail": result.error or "Capture failed"},
        )
    return result.to_dict()


@router.post("/find")
async def find_element(request: FindRequest):
    """
    Find a UI element by name or control type in the target window.
    """
    # Resolve HWND
    hwnd = request.hwnd
    if hwnd is None:
        fw = uia_inspector.get_foreground_window()
        if not fw["success"]:
            return JSONResponse(
                status_code=503,
                content={"error": True, "detail": "Cannot determine foreground window"},
            )
        hwnd = fw["window"]["hwnd"]

    if request.name:
        result = uia_inspector.find_element_by_name(
            hwnd, request.name, exact=request.exact_name
        )
        return result

    if request.control_type:
        result = uia_inspector.find_element_by_type(hwnd, request.control_type)
        return result

    raise HTTPException(
        status_code=422,
        detail="Provide at least 'name' or 'control_type' in the request body",
    )


@router.get("/status")
async def get_perception_status():
    """Return UIA + screen capture subsystem status."""
    return perception_service.get_status()
