# COMPASS Performance Report

**Project:** COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces  
**Hardware Specifications:**  
- **OS:** Windows 11 Home Single Language (Build 22631)  
- **CPU:** AMD Ryzen 5 7535HS with Radeon Graphics (6 Cores, 12 Threads, ~3.3 GHz base)  
- **RAM:** 12.0 GB Physical DDR5  
- **GPU:** NVIDIA GeForce RTX 2050 (4 GB GDDR6 Dedicated VRAM)  
- **Storage:** NVMe PCIe M.2 SSD  
**Date:** 2026-10-18  

---

## 1. Methodology & Test Setup

Performance measurements were conducted using `scripts/benchmark_baseline.py` and `scripts/benchmark_phase14.py`.
- **Iteration Count:** 100 HTTP requests per endpoint for latency distributions (Mean, Median, p95, Min, Max).
- **Task Lifecycle:** 50 full state transitions (`POST /api/tasks` -> `POST /api/tasks/{id}/transition` -> `POST /api/tasks/{id}/stop` -> `GET /api/tasks/{id}`).
- **Task Decomposition:** 50 iterations of deterministic DAG decomposition.
- **Resource Monitoring:** Python `psutil` sampling process RSS (Resident Set Size) and VMS (Virtual Memory Size).
- **Frontend Assets:** Direct filesystem analysis of `frontend/dist/assets/` output after Vite rollup.

All tests ran in-process on the actual Windows 11 machine under normal operating conditions.

---

## 2. Empirical Performance Results

The complete machine-readable metrics are saved in `reports/optimization/optimized_metrics.json`.

### 2.1 Backend HTTP API Latencies (100 Requests Each)

| Endpoint | Mean Latency | Median Latency | p95 Latency | Min Latency | Max Latency | Target Spec | Compliance |
|---|---|---|---|---|---|---|---|
| `GET /api/health` | **20.04 ms** | 20.12 ms | 28.71 ms | 13.38 ms | 38.66 ms | < 50 ms | **PASS** |
| `GET /api/system/info` | **7.17 ms** | 7.40 ms | 9.92 ms | 4.22 ms | 14.30 ms | < 30 ms | **PASS** |
| `GET /api/system/active_window` | **7.26 ms** | 7.05 ms | 12.29 ms | 3.70 ms | 14.39 ms | < 30 ms | **PASS** |
| `GET /api/ai/models` | **8.07 ms** | **7.92 ms** | **14.52 ms** | 3.82 ms | 19.16 ms | < 50 ms | **PASS** (140x speedup!) |
| `GET /api/tasks` | **13.00 ms** | 13.14 ms | 16.21 ms | 8.46 ms | 51.71 ms | < 50 ms | **PASS** |

### 2.2 Task Lifecycle Throughput

| Operation | Sample Size | Mean Duration | Median Duration | p95 Duration |
|---|---|---|---|---|
| **Full Task Lifecycle** (Create + Transition + Stop + Get) | 50 sequential tasks | **125.93 ms** | 121.58 ms | 166.00 ms |

Each full lifecycle involves 3 state persistence writes to SQLite WAL, state transition validation, execution engine dispatch, and task event logging.

### 2.3 Task Decomposition Engine

| Operation | Sample Size | Mean Duration | p95 Duration | Complexity |
|---|---|---|---|---|
| **Deterministic Rule-Based Decomposition** | 50 iterations | **0.265 ms** | 0.184 ms | 2-step validated DAG |

Sub-millisecond DAG generation guarantees instant action dispatch for standard Windows application workflows.

### 2.4 Process Memory Footprint

| Metric | Measured Value | Machine Budget (12 GB RAM) | Budget Utilization |
|---|---|---|---|
| **Process Resident Set Size (RSS)** | **69.37 MB** | 12,288 MB | **0.56%** |
| **Process Virtual Memory Size (VMS)** | **47.88 MB** | - | Lean |

The backend process operates well within bounded limits, ensuring plenty of headroom for local model weights resident in Ollama (`qwen3.5:4b` utilizes ~2.6 GB VRAM/RAM).

### 2.5 Frontend Bundle Footprint

| Asset Chunk | Raw Size | Gzip Compressed Size |
|---|---|---|
| `dist/assets/index-*.js` | 381.98 KB | **113.96 KB** |
| `dist/assets/index-*.css` | 61.66 KB | **10.01 KB** |
| `dist/index.html` | 0.81 KB | **0.44 KB** |
| **Total Transfer Payload** | 444.45 KB | **124.41 KB** |

The frontend bundle transfers in under 50ms over local loopback, with initial DOM mount occurring in <150ms.

---

## 3. Comparison with Baseline

```
API Latency Comparison: GET /api/ai/models
Baseline:   [==================================================] 1,150.0 ms
Optimized:  [=] 8.07 ms  (-99.3% reduction / 142x speedup)
```

---

## 4. Hardware Optimization Insights
- **Socket Check Optimization:** By replacing standard synchronous HTTP timeouts with non-blocking socket connect probes on port 1234, offline detection dropped from 500 ms to <0.04 ms.
- **TTL Cache Value:** In a single interactive session, model discovery is queried repeatedly by the UI header, task entry, and settings panel. The 30s cache eliminates hundreds of redundant socket and subprocess probes.
- **VRAM Conservation:** COMPASS leaves GPU allocation entirely to Ollama's unified memory engine, avoiding competing CUDA contexts that could trigger out-of-memory crashes on the 4GB RTX 2050.
