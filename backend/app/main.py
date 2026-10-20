"""
COMPASS FastAPI Main Application
Lifespan event management, CORS configuration, exception handlers, and API routing.
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.config import settings
from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.routers import (
    automation,
    health,
    perception,
    planner,
    reliability,
    system,
    tasks,
    workflows,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database & verify storage
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version} in [{settings.environment}] mode..."
    )
    # Enable per-monitor DPI awareness so Win32 coordinate calculations match native display pixels
    try:
        from overlay.win32_helper import set_dpi_awareness
        if set_dpi_awareness():
            logger.info("Windows Per-Monitor DPI awareness successfully enabled")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Notice: Could not set DPI awareness: {e}")

    db.init_db()
    logger.info(f"Database ready at: {settings.database_path}")
    # Phase 2: Initialize action_log table
    from automation.action_log import ensure_action_log_table

    ensure_action_log_table()
    logger.info("Action audit log table ready")
    # Phase 4: Crash recovery audit for interrupted tasks (§32)
    from planner.crash_recovery import crash_recovery_handler

    interrupted = crash_recovery_handler.recover_interrupted_tasks()
    if interrupted:
        logger.info(
            f"Crash recovery completed: {len(interrupted)} interrupted task(s) marked STOPPED."
        )
    yield
    # Shutdown: Clean resources
    logger.info(f"Shutting down {settings.app_name}... All resources released.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# Request Timing and Access Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({process_time}ms)"
    )
    response.headers["X-Process-Time-Ms"] = str(process_time)
    return response


# Permitted local origins for frontend integration (COMPASS-AUDIT-016 fix)
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
custom_origins = os.environ.get("COMPASS_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in custom_origins.split(",") if o.strip()] or DEFAULT_ALLOWED_ORIGINS


@app.middleware("http")
async def validate_browser_origin(request: Request, call_next):
    """Origin boundary defense middleware: Prevents hostile web origins from hijacking local control."""
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS and request.url.path.startswith("/api/"):
        logger.warning(
            f"Blocked unauthorized cross-origin request from '{origin}' to '{request.url.path}'"
        )
        return JSONResponse(
            status_code=403,
            content={
                "error": True,
                "detail": f"Origin '{origin}' is not authorized for local API control.",
            },
        )
    return await call_next(request)


# CORS Configuration — explicit origin trust boundary
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Error Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "status_code": exc.status_code, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "")
        errors.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content={
            "error": True,
            "status_code": 422,
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        f"Unhandled exception during {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status_code": 500,
            "detail": "Internal server error occurred.",
        },
    )


# Include Routers
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(system.router)
app.include_router(perception.router)
app.include_router(automation.router)
app.include_router(planner.router)
app.include_router(workflows.router)
app.include_router(reliability.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs": "/api/docs",
        "health": "/api/health",
    }
