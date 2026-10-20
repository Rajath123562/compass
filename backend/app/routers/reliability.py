import asyncio
import json
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.config import settings
from backend.app.database import db

router = APIRouter(prefix="/api/reliability", tags=["reliability"])


@router.get("/health")
async def get_health():
    """
    Returns system health according to Phase 9 diagnostic constraints.
    """
    # Just basic DB health for now
    db_health = db.check_health()
    status = "HEALTHY" if db_health.get("status") == "healthy" else "CRITICAL"

    return {
        "status": status,
        "app": settings.app_name,
        "version": settings.app_version,
        "uptime_seconds": 0.0,  # Dummy for now
        "timestamp": time.time(),
        "database": db_health,
        "system": {},
    }


# Global queues for SSE broadcasting
event_queues = []


def broadcast_event(event: dict):
    # This function should be called whenever an incident is emitted
    data = json.dumps(event)
    for q in event_queues:
        q.put_nowait(f"data: {data}\n\n")


@router.get("/events")
async def get_events():
    """SSE endpoint for reliability events"""

    async def event_generator():
        q = asyncio.Queue()
        event_queues.append(q)
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            event_queues.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
