"""
COMPASS System Router
System telemetry and safe localhost shutdown.
"""

import asyncio
import os
import platform
import time

import psutil
from fastapi import APIRouter, HTTPException, Request, status

from backend.app.logging_config import logger
from backend.app.models import (
    ActiveWindowResponse,
    ShutdownResponse,
    SystemInfoResponse,
)

router = APIRouter(prefix="/api/system", tags=["System"])

START_TIME = time.time()


@router.get("/info", response_model=SystemInfoResponse)
async def get_system_info():
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info()
    sys_mem = psutil.virtual_memory()

    return SystemInfoResponse(
        os=platform.system(),
        os_version=f"{platform.release()} (build {platform.version()})",
        python_version=platform.python_version(),
        cpu_percent=round(proc.cpu_percent(interval=None), 1),
        memory_used_mb=round(mem.rss / (1024 * 1024), 2),
        memory_total_mb=round(sys_mem.total / (1024 * 1024), 2),
        process_pid=os.getpid(),
        uptime_seconds=round(time.time() - START_TIME, 2),
    )


@router.get("/active_window", response_model=ActiveWindowResponse)
async def get_active_window():
    """Return active foreground window title, process name, and status in <5ms."""
    if platform.system() == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    pname = "unknown"
                    if pid.value:
                        try:
                            pname = psutil.Process(pid.value).name()
                        except Exception:
                            pname = "unknown"
                    return ActiveWindowResponse(
                        app_name=pname,
                        window_title=title or "Active Window",
                        process_id=int(pid.value),
                        hwnd=int(hwnd),
                        status="active",
                    )
        except Exception as e:
            logger.debug(f"Active window detection fallback: {e}")

    return ActiveWindowResponse(
        app_name="Desktop Workspace",
        window_title="Active Desktop Workspace",
        process_id=0,
        hwnd=0,
        status="ambient",
    )


@router.get("/diagnostics")
async def get_diagnostics():
    """Generate and return zero-knowledge redacted diagnostic bundle."""
    from scripts.export_diagnostic_bundle import generate_diagnostic_bundle
    bundle = generate_diagnostic_bundle()
    return bundle


@router.post("/shutdown", response_model=ShutdownResponse)
async def shutdown_system(request: Request):
    client_host = request.client.host if request.client else ""
    # Enforce strictly localhost callers
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        logger.warning(f"Unauthorized shutdown attempt from remote host: {client_host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shutdown endpoint is restricted to localhost callers only.",
        )

    logger.info("Graceful shutdown requested via local API endpoint.")

    # Schedule clean termination after sending HTTP response
    async def delayed_exit():
        await asyncio.sleep(0.5)
        logger.info("Executing clean process termination.")
        # On Windows, os._exit(0) cleanly stops the current process without hung threads
        os._exit(0)

    asyncio.create_task(delayed_exit())

    return ShutdownResponse(
        status="shutting_down",
        message="COMPASS backend server is initiating graceful shutdown.",
    )
