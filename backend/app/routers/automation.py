"""
COMPASS Automation API Router
Safe, validated UI action execution endpoints.

Routes:
  POST /api/automation/click   → click a UI element via UIA
  POST /api/automation/type    → type text into an editable element
  POST /api/automation/key     → send a keyboard key (allowlisted)
  POST /api/automation/focus   → focus a UI element
  GET  /api/automation/log     → recent action audit log

IMPORTANT:
  Arbitrary coordinate-based clicking is NOT exposed as an API.
  All actions require a resolved ElementReference and pass through
  ActionValidator before dispatch. Coordinate-based SendInput is only
  used internally as a fallback after element revalidation.
"""

import time
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from automation import action_dispatcher, action_log
from automation.action_validator import ActionValidator

router = APIRouter(prefix="/api/automation", tags=["automation"])

# Action validator with foreground context checking enabled
_validator = ActionValidator(check_foreground=True)


# ─── Request Models ────────────────────────────────────────────────────────────


class ElementRefRequest(BaseModel):
    """Identifies the target element by its reference properties."""

    hwnd: int = Field(..., description="Window handle containing the element")
    runtime_id: str = Field(default="", description="UIA runtime ID (most reliable)")
    automation_id: str = Field(default="", description="UIA AutomationId")
    control_type: str = Field(
        default="", description="Control type (e.g., 'Edit', 'Button')"
    )
    name: str = Field(default="", description="Element accessible name")
    bounds: dict[str, int] = Field(
        default_factory=dict, description="Last known bounding rect"
    )
    window_title: str = Field(default="", description="Parent window title")
    process_id: int = Field(default=0, description="Owning process ID")


class ClickRequest(BaseModel):
    element: ElementRefRequest
    task_id: str | None = Field(default=None)


class TypeRequest(BaseModel):
    element: ElementRefRequest
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Text to type. Content is NOT stored in logs.",
    )
    task_id: str | None = Field(default=None)


class KeyRequest(BaseModel):
    key: str = Field(..., description="Key name (e.g., 'enter', 'escape', 'tab')")
    task_id: str | None = Field(default=None)


class FocusRequest(BaseModel):
    element: ElementRefRequest
    task_id: str | None = Field(default=None)


# ─── Helper ───────────────────────────────────────────────────────────────────


def _element_ref_to_dict(ref: ElementRefRequest) -> dict[str, Any]:
    """Convert ElementRefRequest Pydantic model to dict for validator/dispatcher."""
    return {
        "hwnd": ref.hwnd,
        "runtime_id": ref.runtime_id,
        "automation_id": ref.automation_id,
        "control_type": ref.control_type,
        "name": ref.name,
        "bounds": ref.bounds,
        "window_title": ref.window_title,
        "process_id": ref.process_id,
    }


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post("/click")
async def click_element(request: ClickRequest):
    """
    Click a UI element identified by its ElementReference.
    Runs full validation pipeline before dispatching action.
    """
    el_dict = _element_ref_to_dict(request.element)

    validation = _validator.validate_click(el_dict)
    if not validation.ok:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "detail": f"Validation failed: {validation.reason}",
            },
        )

    # Use fresh validated element snapshot for dispatch
    fresh_el = validation.element_snapshot or el_dict
    result = action_dispatcher.click_element(fresh_el, task_id=request.task_id)
    return result.to_dict()


@router.post("/type")
async def type_text(request: TypeRequest):
    """
    Type text into an editable element.
    Text content is NOT stored in the audit log — only text_length is recorded.
    """
    el_dict = _element_ref_to_dict(request.element)

    validation = _validator.validate_type(el_dict, request.text)
    if not validation.ok:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "detail": f"Validation failed: {validation.reason}",
            },
        )

    fresh_el = validation.element_snapshot or el_dict
    result = action_dispatcher.type_text(
        fresh_el, request.text, task_id=request.task_id
    )
    return result.to_dict()


@router.post("/key")
async def send_key(request: KeyRequest):
    """
    Send a keyboard key. Only keys in the allowed VK_CODES list are accepted.
    """
    validation = _validator.validate_key(request.key)
    if not validation.ok:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "detail": f"Validation failed: {validation.reason}",
            },
        )

    result = action_dispatcher.send_key(request.key, task_id=request.task_id)
    return result.to_dict()


@router.post("/focus")
async def focus_element(request: FocusRequest):
    """
    Set keyboard focus on a UI element.
    """
    el_dict = _element_ref_to_dict(request.element)

    validation = _validator.validate_focus(el_dict)
    if not validation.ok:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "detail": f"Validation failed: {validation.reason}",
            },
        )

    fresh_el = validation.element_snapshot or el_dict
    result = action_dispatcher.focus_element(fresh_el, task_id=request.task_id)
    return result.to_dict()


@router.get("/log")
async def get_action_log(
    limit: int = Query(default=50, ge=1, le=500),
    task_id: str | None = Query(default=None),
):
    """
    Return recent action audit log entries (newest first).
    Text content is never stored — only metadata (text_length, action_type, result).
    """
    logs = action_log.get_recent_logs(limit=limit, task_id=task_id)
    return {
        "count": len(logs),
        "entries": logs,
        "timestamp": time.time(),
    }
