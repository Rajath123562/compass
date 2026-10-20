"""
COMPASS Resource Baseline Measurement Script
Measures real memory footprint, CPU utilization, startup time, and API latencies on Windows 11.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
OUTPUT_FILE = ROOT_DIR / "docs" / "resource_baseline.json"


def measure():
    print("=" * 60)
    print("COMPASS — RESOURCE BASELINE MEASUREMENT")
    print("=" * 60)

    # 1. Measure Backend Startup Time & Resource
    print("[1/4] Starting backend server...")
    start_t = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)

    cmd = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    backend_proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Poll until ready
    ready = False
    ready_t = 0.0
    for _ in range(30):
        try:
            r = requests.get("http://127.0.0.1:8000/api/health", timeout=0.5)
            if r.status_code == 200:
                ready_t = time.perf_counter()
                ready = True
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.1)

    if not ready:
        backend_proc.kill()
        print("[ERROR] Backend did not respond within timeout.")
        return None

    startup_time_ms = round((ready_t - start_t) * 1000, 2)
    print(f"  Backend Startup Time: {startup_time_ms} ms")

    # Measure process memory and CPU
    proc = psutil.Process(backend_proc.pid)
    backend_mem_rss_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
    backend_cpu_pct = round(proc.cpu_percent(interval=0.2), 1)
    print(f"  Backend Memory (RSS): {backend_mem_rss_mb} MB")
    print(f"  Backend CPU:          {backend_cpu_pct}%")

    # 2. Measure API Latencies
    print("[2/4] Benchmarking API latencies (10 sample rounds)...")
    endpoints = [
        ("GET /api/health", "http://127.0.0.1:8000/api/health", "GET", None),
        ("GET /api/system/info", "http://127.0.0.1:8000/api/system/info", "GET", None),
        (
            "POST /api/tasks",
            "http://127.0.0.1:8000/api/tasks",
            "POST",
            {"goal": "Benchmark task execution"},
        ),
    ]

    latencies = {}
    created_task_id = None

    for label, url, method, payload in endpoints:
        samples = []
        for _ in range(10):
            t0 = time.perf_counter()
            if method == "GET":
                resp = requests.get(url, timeout=2.0)
            else:
                resp = requests.post(url, json=payload, timeout=2.0)
                if resp.status_code == 201 and not created_task_id:
                    created_task_id = resp.json().get("id")
            t1 = time.perf_counter()
            samples.append((t1 - t0) * 1000)
        avg_ms = round(sum(samples) / len(samples), 2)
        min_ms = round(min(samples), 2)
        max_ms = round(max(samples), 2)
        latencies[label] = {"avg_ms": avg_ms, "min_ms": min_ms, "max_ms": max_ms}
        print(f"  {label:<22}: Avg {avg_ms} ms | Min {min_ms} ms | Max {max_ms} ms")

    # 3. Measure Overlay Startup and Memory
    print("[3/4] Measuring PySide6 Overlay startup & memory...")
    overlay_cmd = [str(VENV_PYTHON), "-m", "overlay.launcher", "--duration", "2.0"]
    ov_start = time.perf_counter()
    ov_proc = subprocess.Popen(
        overlay_cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.6)

    overlay_mem_rss_mb = 0.0
    if psutil.pid_exists(ov_proc.pid):
        try:
            ov_p = psutil.Process(ov_proc.pid)
            overlay_mem_rss_mb = round(ov_p.memory_info().rss / (1024 * 1024), 2)
        except Exception:  # noqa: BLE001, S110
            pass
    ov_proc.wait(timeout=5)
    ov_exit_t = time.perf_counter()
    overlay_startup_est_ms = round((ov_exit_t - ov_start - 2.0) * 1000, 2)  # noqa: F841
    print(f"  Overlay Memory (RSS): {overlay_mem_rss_mb} MB")

    # 4. Clean shutdown
    print("[4/4] Shutting down backend cleanly...")
    try:
        requests.post("http://127.0.0.1:8000/api/system/shutdown", timeout=1.0)
    except Exception:  # noqa: BLE001, S110
        pass
    time.sleep(1)
    if backend_proc.poll() is None:
        backend_proc.terminate()
        backend_proc.wait(timeout=3)

    total_core_memory_mb = round(backend_mem_rss_mb + overlay_mem_rss_mb, 2)
    print("-" * 60)
    print(
        f"TOTAL CORE MEMORY (Backend + Overlay): {total_core_memory_mb} MB (Target: < 150 MB)"
    )
    print("=" * 60)

    results = {
        "timestamp": time.time(),
        "hardware": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "cpu_cores": psutil.cpu_count(logical=True),
            "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        },
        "backend": {
            "startup_time_ms": startup_time_ms,
            "memory_rss_mb": backend_mem_rss_mb,
            "cpu_percent": backend_cpu_pct,
        },
        "overlay": {"memory_rss_mb": overlay_mem_rss_mb},
        "total_combined_memory_mb": total_core_memory_mb,
        "api_latencies": latencies,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"Saved baseline report to: {OUTPUT_FILE}")
    return results


if __name__ == "__main__":
    res = measure()
    sys.exit(0 if res else 1)
