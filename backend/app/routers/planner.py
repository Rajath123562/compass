"""
COMPASS Phase 3 Planner & AI Routing API
Exposes endpoints for plan generation, task execution, task cancellation,
model discovery, and live task lifecycle streaming via Server-Sent Events (SSE).
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.database import db
from backend.app.services.task_service import task_service
from planner.execution_engine import execution_engine
from planner.planner_service import planner_service
from providers.omniroute_provider import OmniRouteProvider

router = APIRouter(prefix="/api", tags=["Planner & AI"])

# Global OmniRoute provider instance
_omniroute_provider = OmniRouteProvider()


# ─── Request / Response Schemas ────────────────────────────────────────────────


class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=2, max_length=1000, description="User goal")
    ui_snapshot: dict[str, Any] | None = Field(
        default=None, description="Optional UI snapshot (captured live if omitted)"
    )
    task_id: str | None = Field(
        default=None, description="Optional associated task ID"
    )
    model: str | None = Field(
        default=None, description="Optional requested model ID"
    )


class RunTaskRequest(BaseModel):
    model: str | None = Field(default=None, description="Optional model to use")


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/ai/status")
async def get_ai_status():
    """
    Get live AI gateway connectivity, provider status, free-only policy, and system hardware.
    Never exposes API keys or credentials.
    """
    healthy, msg = _omniroute_provider.check_health()
    active_model = _omniroute_provider.select_active_model()
    permitted_models = _omniroute_provider.get_permitted_models()

    from providers.hardware_detector import get_system_hardware
    from providers.claude_computer_use_adapter import ClaudeComputerUseClient
    from providers.gemini_provider import get_gemini_provider
    claude_client = ClaudeComputerUseClient()
    gemini_client = get_gemini_provider()

    return {
        "status": "online" if healthy else "unavailable",
        "gateway": _omniroute_provider.base_url,
        "is_authenticated": _omniroute_provider.resolve_api_key() is not None,
        "free_only_policy": _omniroute_provider.free_only,
        "active_model": active_model,
        "permitted_models_count": len(permitted_models),
        "health_message": msg,
        "hardware": get_system_hardware(),
        "claude_computer_use": {
            "model": "claude-opus-5-5",
            "toolset": "computer_toolset_20260801",
            "is_configured": claude_client.is_configured,
            "status": "ready" if claude_client.is_configured else "needs_key",
        },
        "gemini": {
            "model": gemini_client.default_model,
            "is_configured": gemini_client.is_available,
            "status": "ready" if gemini_client.is_available else "needs_key",
            "budget": gemini_client.budget_manager.get_summary(),
        },
    }


@router.get("/ai/circuit_breaker")
async def get_circuit_breaker_status():
    from planner.circuit_breaker import ai_circuit_breaker
    return {
        "state": ai_circuit_breaker.state.value,
        "can_execute": ai_circuit_breaker.can_execute(),
    }


@router.post("/ai/circuit_breaker/reset")
async def reset_circuit_breaker():
    from planner.circuit_breaker import ai_circuit_breaker
    ai_circuit_breaker.reset()
    return {
        "success": True,
        "state": ai_circuit_breaker.state.value,
        "message": "AI circuit breaker manually reset to CLOSED",
    }


class ClaudeConfigRequest(BaseModel):
    api_key: str | None = None
    opt_in_consent: bool | None = None


class GeminiConfigRequest(BaseModel):
    api_key: str | None = None


@router.get("/ai/claude_status")
async def get_claude_status():
    from providers.claude_computer_use_adapter import ClaudeComputerUseClient
    client = ClaudeComputerUseClient()
    return {
        "model": "claude-opus-5-5",
        "toolset": "computer_toolset_20260801",
        "is_configured": client.is_configured,
        "status": "ready" if client.is_configured else "needs_key",
        "beta_header": "computer-use-2026-08-01",
    }


@router.post("/ai/claude_config")
async def update_claude_config(cfg: ClaudeConfigRequest):
    if cfg.api_key:
        os.environ["ANTHROPIC_API_KEY"] = cfg.api_key.strip()
    from providers.claude_computer_use_adapter import ClaudeComputerUseClient
    client = ClaudeComputerUseClient()
    return {
        "success": True,
        "is_configured": client.is_configured,
        "model": "claude-opus-5-5",
        "toolset": "computer_toolset_20260801",
    }


@router.get("/ai/gemini_status")
async def get_gemini_status():
    from providers.gemini_provider import get_gemini_provider
    client = get_gemini_provider()
    return {
        "model": client.default_model,
        "is_configured": client.is_available,
        "status": "ready" if client.is_available else "needs_key",
        "budget": client.budget_manager.get_summary(),
    }


@router.post("/ai/gemini_config")
async def update_gemini_config(cfg: GeminiConfigRequest):
    from providers.gemini_provider import get_gemini_provider
    client = get_gemini_provider()
    if cfg.api_key:
        client.set_api_key(cfg.api_key.strip())
    return {
        "success": True,
        "is_configured": client.is_available,
        "model": client.default_model,
    }


@router.get("/ai/models")
async def get_ai_models(
    free_only: bool = Query(default=True, description="Filter for free-only models"),
):
    """
    List discovered AI models with normalized capability and cost metadata.
    Safe for public display; never exposes secrets.
    """
    if free_only:
        models = _omniroute_provider.get_permitted_models()
    else:
        models = _omniroute_provider.discover_models()

    return {
        "count": len(models),
        "free_only_filter": free_only,
        "models": [m.to_safe_dict() for m in models],
    }


@router.post("/planner/plan")
async def generate_plan(req: PlanRequest):
    """
    Generate an AI TaskPlan for a goal using live or provided UI perception.
    """
    # Resolve or create task_id
    task_id = req.task_id
    if not task_id:
        task = task_service.create_task(
            goal=req.goal, metadata={"source": "api_planner"}
        )
        task_id = task["id"]

    # Resolve UI snapshot (live foreground capture if none provided)
    ui_snapshot = req.ui_snapshot
    if not ui_snapshot:
        from perception import uia_inspector

        fw = uia_inspector.get_foreground_window()
        win = fw.get("window") or {}
        hwnd = win.get("hwnd") if fw.get("success") else None
        tree = (
            uia_inspector.get_element_tree(hwnd, depth=3, max_elements=50)
            if hwnd
            else {"elements": []}
        )
        ui_snapshot = {"window": win, "elements": tree.get("elements") or []}

    success, plan, err = planner_service.create_plan(
        goal=req.goal, ui_snapshot=ui_snapshot, task_id=task_id, model=req.model
    )

    if not success or not plan:
        raise HTTPException(status_code=502, detail=f"Planning failed: {err}")

    return {"success": True, "task_id": task_id, "plan": plan.model_dump()}


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str, background_tasks: BackgroundTasks):
    """
    Start closed-loop execution for a task in the background.
    Protected by task-scoped execution lock.
    """
    task = task_service.get_task(task_id)

    # Check if already stopped, cancelled, failed, or completed
    state = task.get("state")
    if state in ("COMPLETED", "STOPPED", "CANCELLED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run a task in terminal/stopped state '{state}'.",
        )

    # Spawn background runner thread
    def run_worker():
        execution_engine.run_task(task_id=task_id)

    background_tasks.add_task(run_worker)

    return {
        "success": True,
        "message": f"Task [{task_id}] execution initiated.",
        "task_id": task_id,
    }


@router.get("/tasks/{task_id}/plan")
async def get_task_plan(task_id: str):
    """
    Retrieve the active TaskPlan for a task if one has been generated.
    """
    plan = execution_engine.get_active_plan(task_id)
    if not plan:
        # Check task events in DB for planning_completed
        events = db.get_task_events(task_id)
        for ev in reversed(events):
            if ev.get("event_type") == "planning_completed":
                return {"task_id": task_id, "plan_summary": ev.get("payload")}
        raise HTTPException(
            status_code=404, detail=f"No active plan found for task [{task_id}]."
        )

    return {"task_id": task_id, "plan": plan.model_dump()}


@router.get("/tasks/{task_id}/state")
async def get_task_state(task_id: str):
    """
    Get detailed execution state, recent events, and stop status for a task.
    """
    task = task_service.get_task_detail(task_id)
    task["is_stopped"] = execution_engine.is_stopped(task_id)
    return task


@router.get("/tasks/{task_id}/events")
async def stream_task_events(task_id: str, request: Request):
    """
    Stream live task lifecycle events via Server-Sent Events (SSE).
    """
    task_service.get_task(task_id)  # Validate exists

    async def event_generator():
        last_event_id = 0
        while True:
            if await request.is_disconnected():
                break

            events = db.get_task_events(task_id)
            new_events = [e for e in events if e.get("id", 0) > last_event_id]

            for ev in new_events:
                last_event_id = max(last_event_id, ev.get("id", 0))
                data = json.dumps(ev)
                yield f"event: {ev.get('event_type')}\ndata: {data}\n\n"

            # Check if task reached a terminal state
            curr_task = db.get_task(task_id)
            if (
                curr_task
                and curr_task.get("state")
                in [
                    "COMPLETED",
                    "FAILED",
                    "STOPPED",
                    "CANCELLED",
                    "BLOCKED",
                    "UNVERIFIED",
                    "AI_UNAVAILABLE",
                    "SAFETY_BLOCKED",
                ]
                and not new_events
            ):
                yield f"event: task_end\ndata: {json.dumps({'state': curr_task.get('state')})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ─── Phase 4 Extended Endpoints ────────────────────────────────────────────────


class GoalUnderstandRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=1000)


class ConfirmActionRequest(BaseModel):
    decision_id: str
    approved: bool
    reason: str | None = None


class SetModeRequest(BaseModel):
    mode: str


@router.post("/planner/goal/understand")
async def understand_goal_endpoint(req: GoalUnderstandRequest):
    """
    Parse natural language goal intent, extract target app, constraints, and ambiguity.
    """
    from planner.goal_understanding import goal_understanding_engine

    res = goal_understanding_engine.understand_goal(req.goal)
    return res.model_dump()


@router.get("/planner/pending-approval/{task_id}")
async def get_pending_task_approval(task_id: str):
    """
    Retrieve any active pending approval record for a task awaiting human confirmation.
    """
    from planner.human_approval import human_approval_controller

    appr = human_approval_controller.get_pending_approval_for_task(task_id)
    if not appr:
        return {"has_pending": False, "approval": None}

    return {
        "has_pending": True,
        "approval": {
            "approval_id": appr.approval_id,
            "decision_id": appr.decision_id,
            "action_type": appr.action_type,
            "target_description": appr.target_description,
            "explanation": appr.explanation,
            "risk_level": appr.risk_level,
            "expires_at": appr.expires_at,
            "remaining_seconds": max(0.0, round(appr.expires_at - time.time(), 1)),
        },
    }


@router.post("/planner/confirm/{task_id}")
async def confirm_task_action(task_id: str, req: ConfirmActionRequest):
    """
    Explicit human approval or rejection for a pending decision in any guidance mode (§33).
    Strictly validates task existence, non-terminal state, and decision ID binding.
    """
    from backend.app.models import TaskState
    from planner.human_approval import ApprovalState, human_approval_controller

    # 1. Validate task existence
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # 2. Validate task is not in a terminal state
    task_state = task.get("state")
    if task_state in [
        TaskState.COMPLETED.value,
        TaskState.FAILED.value,
        TaskState.STOPPED.value,
        TaskState.CANCELLED.value,
    ]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot confirm action for task in terminal state '{task_state}'",
        )

    # 3. Validate approval record exists
    appr = human_approval_controller.get_approval(task_id, req.decision_id)
    if not appr:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request for decision '{req.decision_id}' on task '{task_id}' not found",
        )

    if appr.state == ApprovalState.CONSUMED:
        raise HTTPException(
            status_code=409, detail="Approval token has already been consumed"
        )

    if appr.state == ApprovalState.INVALIDATED:
        raise HTTPException(
            status_code=410,
            detail=f"Approval request was invalidated: {appr.invalidation_reason or 'expired'}",
        )

    if appr.state != ApprovalState.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Approval request is in state '{appr.state.value}', not PENDING",
        )

    if req.approved:
        ok = human_approval_controller.grant_approval(task_id, req.decision_id)
        if not ok:
            raise HTTPException(
                status_code=400, detail="Failed to grant approval request"
            )
        return {"success": True, "status": "GRANTED", "decision_id": req.decision_id}
    else:
        ok = human_approval_controller.reject_approval(
            task_id, req.decision_id, reason=req.reason or "User rejected"
        )
        if not ok:
            raise HTTPException(
                status_code=400, detail="Failed to reject approval request"
            )
        return {"success": True, "status": "REJECTED", "decision_id": req.decision_id}


@router.get("/planner/timeline/{task_id}")
async def get_task_timeline(task_id: str):
    """
    Query full observability timeline entries for a task without exposing model secrets.
    """
    entries = execution_engine.get_timeline(task_id)
    return {
        "task_id": task_id,
        "count": len(entries),
        "timeline": [e.model_dump() for e in entries],
    }


@router.get("/planner/mode")
async def get_guidance_mode():
    """Get current guidance mode (GUIDE, ASSIST, CONFIRM, AUTONOMOUS)."""
    from planner.human_approval import human_approval_controller

    return {"mode": human_approval_controller.mode.value}


@router.post("/planner/mode")
async def set_guidance_mode(req: SetModeRequest):
    """Set guidance mode (GUIDE, ASSIST, CONFIRM, AUTONOMOUS)."""
    from planner.human_approval import human_approval_controller
    from planner.models import GuidanceMode

    try:
        new_mode = GuidanceMode(req.mode.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid guidance mode '{req.mode}'. Allowed: GUIDE, ASSIST, CONFIRM, AUTONOMOUS",
        )
    human_approval_controller.set_mode(new_mode)
    return {"success": True, "mode": new_mode.value}


@router.get("/planner/resources")
async def get_resources():
    """Get measured hardware and process resource breakdown."""
    from planner.resource_governor import resource_governor

    snapshot = resource_governor.measure_resources()
    return snapshot.model_dump()
