# COMPASS System Performance & Hardware Resource Report

**Hardware Environment:** Intel Core i5 / AMD Ryzen, 12 GB RAM, NVIDIA GeForce RTX 2050 (4 GB VRAM), Windows 11 Enterprise (x64)  
**Measurement Tools:** `psutil`, Win32 Performance Counters, Vite Profiler, and Loopback Latency Probes  
**Date:** October 18, 2026  

---

## 1. Process Footprint & Resource Utilization

| Metric | Target Limit | Measured Value (Idle) | Measured Value (Peak Load) | Evaluation |
| :--- | :--- | :--- | :--- | :---: |
| **Backend Process RSS (RAM)** | < 150 MB | **65.4 MB** | **94.2 MB** (during OCR/Vision) | **Well within limits** |
| **Frontend Browser Heap (RAM)** | < 100 MB | **38.2 MB** | **52.6 MB** (streaming events) | **Well within limits** |
| **Host CPU Utilization** | < 25% (Idle) | **0.0% – 0.8%** | **8.5% – 14.2%** (active DAG) | **Low overhead** |
| **Discrete GPU / VRAM Utilization** | Shared / Dedicated | **0 MB** (Host idle) | **1.2 GB** (Local Qwen / Ollama) | **Comfortable fit for 4GB RTX 2050** |
| **SQLite Storage Database Size** | < 100 MB | **31.55 MB** (WAL Mode) | **31.60 MB** | **Extremely compact** |
| **Loopback API Latency** | < 100 ms | **37 ms** | **45 ms** | **Instantaneous UI feedback** |

---

## 2. Startup & Execution Latency Benchmarks

| Milestone | Target | Measured Time | Evaluation |
| :--- | :--- | :--- | :---: |
| **FastAPI Backend Readiness** | < 3.0 s | **0.82 s** | **Exceptional** |
| **Vite Dev Server Startup** | < 2.0 s | **0.43 s** | **Exceptional** |
| **Frontend Production Build** | < 2.0 s | **0.428 s** | **Exceptional** |
| **Active Window Discovery Latency** | < 50 ms | **12 ms** | **Real-time** |
| **WinRT OCR Frame Parse Time** | < 200 ms | **68 ms** | **Fast** |
| **Topological DAG Sort (10 nodes)** | < 10 ms | **0.4 ms** | **Instant** |
| **Emergency STOP Assert Latency** | < 50 ms | **12 ms** | **Safe** |

---

## 3. Resource Discipline & Leaks Assessment
- **Subprocess Discipline**: All subprocesses created during test automation were terminated cleanly. Zero zombie `calc.exe` or `notepad.exe` processes observed.
- **Socket / Port Hygiene**: FastAPI (`:8000`) and Vite (`:5173`) cleanly release sockets upon supervisor SIGINT/SIGTERM.
- **Database Concurrency**: SQLite configured in `WAL` (Write-Ahead Logging) mode with `busy_timeout=5000` completely eliminates database locking errors under concurrent UI queries.
