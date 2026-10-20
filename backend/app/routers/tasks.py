"""
COMPASS Tasks Router
Endpoints for task creation, retrieval, state transitions, and cancellation.
"""


from fastapi import APIRouter, BackgroundTasks, Query

from backend.app.logging_config import logger
from backend.app.models import (
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    TaskTransition,
)
from backend.app.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(task_in: TaskCreate, background_tasks: BackgroundTasks):
    task = task_service.create_task(goal=task_in.goal, metadata=task_in.metadata)
    task_id = task["id"]

    # Auto-trigger execution in background so the task doesn't sit at STARTING
    def auto_execute():
        try:
            from planner.execution_engine import execution_engine

            logger.info(f"Auto-executing task [{task_id}] goal='{task_in.goal}'")
            execution_engine.run_task(task_id=task_id)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Auto-execution failed for task [{task_id}]: {e}")

    import os
    if not os.environ.get("COMPASS_TEST_MODE"):
        background_tasks.add_task(auto_execute)
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(limit: int = Query(default=50, ge=1, le=100)):
    return task_service.list_tasks(limit=limit)


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str):
    return task_service.get_task_detail(task_id)


@router.post("/{task_id}/transition", response_model=TaskResponse)
async def transition_task_state(task_id: str, transition: TaskTransition):
    return task_service.transition_state(
        task_id=task_id, new_state=transition.new_state, reason=transition.reason or ""
    )


@router.post("/{task_id}/stop", response_model=TaskResponse)
async def stop_task(task_id: str):
    try:
        from planner.execution_engine import execution_engine

        execution_engine.stop_task(
            task_id=task_id, reason="User triggered stop via API"
        )
    except Exception:  # noqa: BLE001, S110
        pass
    return task_service.stop_task(task_id=task_id, reason="User triggered stop via API")


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str):
    try:
        from planner.execution_engine import execution_engine

        execution_engine.stop_task(
            task_id=task_id, reason="User triggered cancel via API"
        )
    except Exception:  # noqa: BLE001, S110
        pass
    return task_service.stop_task(
        task_id=task_id, reason="User triggered cancel via API"
    )


@router.delete("", response_model=dict)
async def clear_completed_tasks():
    """Clear all completed/terminal tasks from database history."""
    return task_service.clear_completed_tasks()


@router.delete("/{task_id}", response_model=dict)
async def delete_task(task_id: str):
    """Delete a specific task and its cascaded events, decisions, and approvals."""
    return task_service.delete_task(task_id=task_id)


from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    model_id: str | None = None

@router.post("/chat")
async def guide_chat(chat_in: ChatMessage):
    """Interactive chat with the COMPASS guide engine."""
    from planner.interactive_guide_engine import interactive_guide_engine
    
    return StreamingResponse(
        interactive_guide_engine.generate_guidance_stream(chat_in.message, model_id=chat_in.model_id),
        media_type="text/plain"
    )

@router.post("/undo")
async def undo_chat_step():
    """Undo the last interactive chat step."""
    from planner.interactive_guide_engine import interactive_guide_engine
    msg = interactive_guide_engine.undo_last_step()
    return {"message": msg}
