"""
COMPASS Phase 8 — Workflows Router
REST API endpoints and SSE event streaming for autonomous workflows.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.database import db
from backend.app.logging_config import logger
from planner.workflow_models import ResourceBudget, RetryPolicy, WorkflowNode
from planner.workflow_orchestrator import WorkflowOrchestrator

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

# Singleton orchestrator instance for backend API
orchestrator = WorkflowOrchestrator(database=db)


class WorkflowNodeCreate(BaseModel):
    node_id: str
    goal: str
    description: str = ""
    operation: str = "ui_action"
    action: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=1, le=10)
    risk_level: str = "LOW"
    approval_required: bool = False
    timeout_s: float = Field(default=60.0, ge=5.0, le=600.0)
    preconditions: list[Any] = Field(default_factory=list)
    postconditions: list[Any] = Field(default_factory=list)


class WorkflowCreateRequest(BaseModel):
    goal: str
    task_id: str | None = None
    workflow_id: str | None = None
    nodes: list[WorkflowNodeCreate]
    resource_budget: dict[str, Any] | None = None
    retry_policy: dict[str, Any] | None = None
    deadline: float | None = None
    metadata: dict[str, Any] | None = None
    auto_start: bool = False


class WorkflowStopRequest(BaseModel):
    reason: str = "User requested stop via API"


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workflow(req: WorkflowCreateRequest):
    """Create and validate a new workflow graph."""
    nodes: list[WorkflowNode] = []
    for n in req.nodes:
        node = WorkflowNode(
            node_id=n.node_id,
            goal=n.goal,
            description=n.description,
            operation=n.operation,
            action=n.action,
            dependencies=n.dependencies,
            priority=n.priority,
            risk_level=n.risk_level,
            approval_required=n.approval_required,
            timeout_s=n.timeout_s,
            preconditions=n.preconditions,
            postconditions=n.postconditions,
        )
        nodes.append(node)

    budget = ResourceBudget(**(req.resource_budget or {}))
    policy = RetryPolicy(**(req.retry_policy or {}))

    try:
        wf = orchestrator.create_workflow(
            goal=req.goal,
            nodes=nodes,
            task_id=req.task_id,
            workflow_id=req.workflow_id,
            resource_budget=budget,
            retry_policy=policy,
            deadline=req.deadline,
            metadata=req.metadata,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    if req.auto_start:
        orchestrator.start_workflow(wf.workflow_id, run_in_background=True)

    return wf.model_dump()


@router.get("")
async def list_workflows(
    limit: int = Query(default=50, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
):
    """List workflows, optionally filtering by status."""
    return db.list_workflows(limit=limit, status=status_filter)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get complete workflow status, progress, and DAG nodes."""
    wf = orchestrator.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404, detail=f"Workflow '{workflow_id}' not found."
        )
    data = wf.model_dump()
    data["progress"] = wf.compute_progress()
    return data


@router.post("/{workflow_id}/start")
async def start_workflow(workflow_id: str):
    """Start execution of a workflow."""
    started = orchestrator.start_workflow(workflow_id, run_in_background=True)
    if not started:
        raise HTTPException(
            status_code=400,
            detail="Failed to start workflow. Check status or resource limits.",
        )
    return {"status": "started", "workflow_id": workflow_id}


@router.post("/{workflow_id}/stop")
async def stop_workflow(workflow_id: str, req: WorkflowStopRequest | None = None):
    """Universal STOP for a running workflow."""
    reason = req.reason if req else "User requested stop via API"
    stopped = orchestrator.stop_workflow(workflow_id, reason=reason)
    if not stopped:
        raise HTTPException(status_code=400, detail="Failed to stop workflow.")
    return {"status": "stopped", "workflow_id": workflow_id, "reason": reason}


@router.post("/{workflow_id}/pause")
async def pause_workflow(workflow_id: str):
    """Pause a running workflow."""
    paused = orchestrator.pause_workflow(workflow_id)
    if not paused:
        raise HTTPException(status_code=400, detail="Failed to pause workflow.")
    return {"status": "paused", "workflow_id": workflow_id}


@router.post("/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    """Resume a paused workflow."""
    resumed = orchestrator.resume_workflow(workflow_id)
    if not resumed:
        raise HTTPException(status_code=400, detail="Failed to resume workflow.")
    return {"status": "resumed", "workflow_id": workflow_id}


@router.post("/{workflow_id}/recover")
async def recover_workflow(workflow_id: str):
    """Recover an interrupted workflow from its HMAC-verified checkpoint."""
    ok, wf, err = orchestrator.recover_workflow(workflow_id)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Recovery failed: {err}")
    return {
        "status": "recovered",
        "workflow_id": workflow_id,
        "generation": wf.execution_generation,
    }


@router.get("/{workflow_id}/events")
async def stream_workflow_events(workflow_id: str):
    """SSE event stream for real-time workflow milestone and node updates."""
    wf = orchestrator.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404, detail=f"Workflow '{workflow_id}' not found."
        )

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def subscriber_cb(event_data: dict[str, Any]):
            loop.call_soon_threadsafe(queue.put_nowait, event_data)

        unsubscribe = orchestrator.subscribe(workflow_id, subscriber_cb)
        try:
            # Yield initial state
            yield f"data: {json.dumps({'event': 'initial_state', 'status': wf.status.value, 'progress': wf.compute_progress()})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield ": ping\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
