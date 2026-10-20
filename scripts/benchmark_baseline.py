import sys
import os
sys.path.insert(0, os.path.abspath("."))
os.environ["COMPASS_TEST_MODE"] = "1"
import time
import statistics
import json
import psutil
from fastapi.testclient import TestClient
from backend.app.main import app

def run_benchmark():
    client = TestClient(app)
    results = {}

    print("--- 1. API Latency Benchmarking (100 iterations each) ---")
    endpoints = [
        ("GET /api/health", lambda: client.get("/api/health")),
        ("GET /api/system/info", lambda: client.get("/api/system/info")),
        ("GET /api/system/active_window", lambda: client.get("/api/system/active_window")),
        ("GET /api/ai/models", lambda: client.get("/api/ai/models")),
        ("GET /api/tasks", lambda: client.get("/api/tasks")),
    ]

    for name, req in endpoints:
        latencies = []
        # Warmup
        for _ in range(5):
            req()
        for _ in range(100):
            t0 = time.perf_counter()
            resp = req()
            t1 = time.perf_counter()
            assert resp.status_code == 200, f"{name} failed with {resp.status_code}"
            latencies.append((t1 - t0) * 1000.0) # in ms

        latencies.sort()
        mean_lat = statistics.mean(latencies)
        median_lat = statistics.median(latencies)
        p95_lat = latencies[int(len(latencies) * 0.95)]
        min_lat = min(latencies)
        max_lat = max(latencies)

        results[name] = {
            "mean_ms": round(mean_lat, 2),
            "median_ms": round(median_lat, 2),
            "p95_ms": round(p95_lat, 2),
            "min_ms": round(min_lat, 2),
            "max_ms": round(max_lat, 2),
        }
        print(f"  {name:30s} Mean: {mean_lat:6.2f}ms | Median: {median_lat:6.2f}ms | p95: {p95_lat:6.2f}ms")

    print("\n--- 2. Task Lifecycle Throughput (50 iterations) ---")
    lifecycle_latencies = []
    for i in range(50):
        t0 = time.perf_counter()
        c = client.post("/api/tasks", json={"goal": f"Benchmark task {i}"})
        tid = c.json()["id"]
        t1 = client.post(f"/api/tasks/{tid}/transition", json={"new_state": "UNDERSTANDING", "reason": "bench"})
        t2 = client.post(f"/api/tasks/{tid}/stop")
        g = client.get(f"/api/tasks/{tid}")
        t_end = time.perf_counter()
        lifecycle_latencies.append((t_end - t0) * 1000.0)

    lifecycle_latencies.sort()
    results["task_lifecycle"] = {
        "mean_ms": round(statistics.mean(lifecycle_latencies), 2),
        "median_ms": round(statistics.median(lifecycle_latencies), 2),
        "p95_ms": round(lifecycle_latencies[int(len(lifecycle_latencies) * 0.95)], 2),
    }
    print(f"  Task Full Lifecycle Mean: {results['task_lifecycle']['mean_ms']:.2f}ms | p95: {results['task_lifecycle']['p95_ms']:.2f}ms")

    print("\n--- 3. Memory & Resource Footprint ---")
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)
    vms_mb = mem_info.vms / (1024 * 1024)
    results["memory"] = {
        "rss_mb": round(rss_mb, 2),
        "vms_mb": round(vms_mb, 2),
    }
    print(f"  Process Memory RSS: {rss_mb:.2f} MB | VMS: {vms_mb:.2f} MB")

    print("\n--- 4. Task Decomposer Latency (Deterministic Rule-Based) ---")
    from planner.task_decomposer import TaskDecomposer
    decomposer = TaskDecomposer()
    decomp_latencies = []
    for i in range(50):
        t0 = time.perf_counter()
        plan = decomposer.decompose(f"bench_task_{i}", "Open Notepad and type 'Hello World'")
        t1 = time.perf_counter()
        decomp_latencies.append((t1 - t0) * 1000.0)

    results["task_decomposition_deterministic"] = {
        "mean_ms": round(statistics.mean(decomp_latencies), 3),
        "p95_ms": round(decomp_latencies[int(len(decomp_latencies) * 0.95)], 3),
        "steps_count": len(plan.steps) if plan else 0
    }
    print(f"  Deterministic Decomposition Mean: {results['task_decomposition_deterministic']['mean_ms']:.3f}ms | p95: {results['task_decomposition_deterministic']['p95_ms']:.3f}ms")

    print("\n--- 5. Frontend Asset Footprint ---")
    dist_dir = os.path.join("frontend", "dist", "assets")
    total_js_bytes = 0
    total_css_bytes = 0
    if os.path.exists(dist_dir):
        for f in os.listdir(dist_dir):
            fp = os.path.join(dist_dir, f)
            if f.endswith(".js"):
                total_js_bytes += os.path.getsize(fp)
            elif f.endswith(".css"):
                total_css_bytes += os.path.getsize(fp)
    results["frontend_bundle"] = {
        "js_kb": round(total_js_bytes / 1024.0, 2),
        "css_kb": round(total_css_bytes / 1024.0, 2),
    }
    print(f"  Frontend JS: {results['frontend_bundle']['js_kb']} KB | CSS: {results['frontend_bundle']['css_kb']} KB")

    out_name = sys.argv[1] if len(sys.argv) > 1 else "baseline_metrics.json"
    out_file = os.path.join("reports", "optimization", out_name)
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark metrics saved to: {out_file}")

if __name__ == "__main__":
    run_benchmark()
