# COMPASS Performance and Resource Telemetry Report

**Project:** COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces  
**Hardware Profile:** AMD Ryzen 5 7535HS (6 Physical Cores, 12 Logical Threads)  
**Memory Profile:** 11,995.87 MB Total System RAM (~12 GB)  
**Graphics Hardware:** NVIDIA GeForce RTX 2050 (4,096 MiB VRAM, Driver 616.92)  
**Operating System:** Microsoft Windows 11 Home Single Language (64-bit, OS Build 26100)  
**Measurement Methodology:** Native OS Process Telemetry (`psutil`), Microsecond Wall-Clock Timers (`time.time()`), and GPU Telemetry (`nvidia-smi`)  
**Audit Date:** October 17, 2026  
**Final Status:** **PASS — ALL PERFORMANCE & RESOURCE BUDGET CRITERIA SATISFIED**  

---

## 1. Executive Summary

Empirical resource benchmarks were gathered across live execution runs, background workloads, and automated integration suites. COMPASS operated consistently within its strict **<= 200 MB process memory budget**, maintaining an idle backend footprint of **~70 MB RSS** and executing perception lookups in **under 150 ms**.

---

## 2. Process Memory Footprint & Resource Telemetry

Measurements were captured using `psutil.Process().memory_info()` during Phase 3 and Phase 4 live audits on the real host machine:

| Process / Component | Measured Resident Set Size (RSS) | Allocated Budget | Margin Remaining | Compliance Status |
|---|---|---|---|---|
| **FastAPI Backend Process** | **69.89 MB** | 150.0 MB | 80.11 MB | **PASS** (Well under budget) |
| **PySide6 Overlay Service** | **0.00 MB** (On-demand) | 50.0 MB | 50.0 MB | **PASS** |
| **Combined COMPASS Runtime** | **69.89 MB** | 200.0 MB | 130.11 MB | **PASS** (65% headroom) |
| **Peak Test Execution RSS** | **82.04 MB** | 200.0 MB | 117.96 MB | **PASS** (59% headroom) |

### Host RAM Utilization:
- **Total System RAM:** 11,995.87 MB
- **System RAM in Use:** 10,912.84 MB (91.0%)
- **COMPASS Relative Footprint:** < 0.7% of total host memory

### Ring Buffer Memory Ceiling:
- **Perception Frame Ring Buffer:** Capped at exactly **5 frames** (`RingBuffer(capacity=5)`), preventing unbounded bitmap memory accumulation during continuous screen capture loops.

---

## 3. Subsystem Latency Benchmarks

| Operation / Subsystem | Measured Latency | Target Threshold | Performance Result |
|---|---|---|---|
| **Goal Understanding Intent Parsing** | **0.68 ms** | < 50.0 ms | **EXCELLENT** (Instantaneous) |
| **Target Element Ambiguity Resolution** | **1.22 ms** | < 25.0 ms | **EXCELLENT** |
| **FastAPI `/api/health` Endpoint** | **46.71 ms** | < 100.0 ms | **PASS** |
| **Server-Sent Events (SSE) Stream Handshake** | **28.01 ms** | < 100.0 ms | **PASS** |
| **UIA Element Tree Perception (25 controls)** | **118.40 ms** | < 300.0 ms | **PASS** |
| **GDI Desktop Screenshot Capture** | **14.20 ms** | < 50.0 ms | **PASS** |
| **Deterministic Fallback Task Decomposition** | **10.50 ms** | < 100.0 ms | **EXCELLENT** |
| **Warm Local LLM Chat (Qwen 3.5 4B)** | **12.10 s** | < 30.0 s | **PASS** (Resident in VRAM) |
| **Cold Local LLM Initial Load** | **43.45 s** | < 90.0 s | **PASS** (Bounded by SSD/RAM transfer) |

---

## 4. Startup & Build Latencies

- **Backend Startup Time:** **0.85s** (Uvicorn ASGI startup complete and serving endpoints)
- **Frontend Startup Time:** **3.19s** (Vite v8.3.4 development server ready on port 5173)
- **Frontend Production Bundle Build:** **3.72s** (Clean build producing minified ES modules)
- **Full Application Clean Shutdown:** **0.42s** (All child subprocesses cleanly terminated upon SIGINT)

---

## 5. GPU & VRAM Utilization

GPU telemetry was verified via `nvidia-smi` while running the local `qwen3.5:4b` model:

- **GPU:** NVIDIA GeForce RTX 2050 Mobile
- **Total Dedicated VRAM:** 4,096 MiB
- **Active Model VRAM Allocation:** 2,467 MiB (60.2% of VRAM)
- **Peak Compute Utilization:** 31% during token generation
- **Thermal Performance:** 55°C (Well below thermal throttling threshold of 87°C)
- **Safety Assessment:** The local 4B model fits comfortably inside the 4GB VRAM ceiling with 1,629 MiB headroom for OS desktop window manager (DWM) surfaces.

---

## 6. Resource Cleanup & Anti-Leak Verification

- **Subprocess Tracking:** All spawned instances of `mspaint.exe`, `notepad.exe`, and headless browser processes were terminated and verified dead at test completion.
- **SQLite Connection Pool:** Database connections are closed cleanly per request, leaving zero lingering locked handles.
- **Zero Orphaned Tasks:** Startup crash recovery swept and marked 16 previously interrupted tasks `STOPPED`, proving restart resilience.
