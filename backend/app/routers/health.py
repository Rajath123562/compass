"""
COMPASS Health Check Router
Performs real probes across database, memory, disk, and process subsystems.
"""

import os
import shutil
import time

import psutil
from fastapi import APIRouter, Response, status

from backend.app.config import settings
from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.models import HealthResponse

router = APIRouter(prefix="/api/health", tags=["Health"])

START_TIME = time.time()


@router.get("", response_model=HealthResponse)
async def get_health(response: Response):
    now = time.time()
    uptime = round(now - START_TIME, 2)

    # 1. Real Database Check
    db_health = db.check_health()
    db_ok = db_health.get("status") == "healthy"

    # 2. System and Resource Telemetry
    try:
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        mem_rss_mb = round(mem_info.rss / (1024 * 1024), 2)
        cpu_pct = round(proc.cpu_percent(interval=None), 1)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to read process stats: {e}")
        mem_rss_mb = 0.0
        cpu_pct = 0.0

    try:
        disk = shutil.disk_usage(str(settings.storage_dir))
        disk_free_gb = round(disk.free / (1024 * 1024 * 1024), 2)
        disk_total_gb = round(disk.total / (1024 * 1024 * 1024), 2)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to read disk usage: {e}")
        disk_free_gb = 0.0
        disk_total_gb = 0.0

    system_telemetry = {
        "pid": os.getpid(),
        "memory_rss_mb": mem_rss_mb,
        "cpu_percent": cpu_pct,
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "environment": settings.environment,
        "test_mode": bool(os.environ.get("COMPASS_TEST_MODE")),
    }

    # Evaluate overall system health
    if db_ok:
        overall_status = "healthy"
    else:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        app=settings.app_name,
        version=settings.app_version,
        uptime_seconds=uptime,
        timestamp=now,
        database=db_health,
        system=system_telemetry,
    )
