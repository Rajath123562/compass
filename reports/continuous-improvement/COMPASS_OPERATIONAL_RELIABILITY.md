# COMPASS Operational Reliability & Runtime Playbook

**Document ID:** COMPASS-OPS-2026-007  
**Target Baseline:** COMPASS v2.0.0-verified.freeze  
**Scope:** Operational Guidelines, Runtime Safety Governors, and Incident Response  
**Date:** 2026-10-18  

---

## 1. Operating Model & High-Level Architecture

COMPASS is designed for supervised, safe desktop automation. It combines real-time screen perception with rigorous fail-closed safety governors to ensure that automation runs only on allowlisted targets and never performs unauthorized or unverified actions.

```
+-----------------------------------------------------------------------------------+
|                              COMPASS Runtime Stack                                |
+-----------------------------------------------------------------------------------+
|  FastAPI Backend (:8000)      <--->      Vite Frontend Console (:5173)            |
|       |                                                                           |
|       +---> AI Safety Circuit Breaker (CLOSED / OPEN / HALF_OPEN)                 |
|       +---> Risk Classifier (LOW / MEDIUM / HIGH / CONSEQUENTIAL)                 |
|       +---> StaleGuard Perception Cache (5000ms TTL / 2000ms High-Risk)           |
|       +---> Action Validator & Foreground Synchronizer                            |
|       +---> Verification Engine (External Observer & WinRT OCR)                  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Safety Governors & Threshold Rules

### 2.1 StaleGuard Perception Freshness
To prevent the agent from acting on outdated screen states (e.g., clicking where a button used to be before a modal popped up), COMPASS enforces the following TTLs:
- **Standard Actions:** Perception data expires after **5,000 milliseconds**.
- **Consequential / High-Risk Actions:** Perception data expires after **2,000 milliseconds**.
- **Invalidation Triggers:** Target window bounds drift, HWND destruction, or focus change immediately invalidates the perception cache and forces a re-observation.

### 2.2 AI Circuit Breaker & Graceful Fallback
The `ai_circuit_breaker` monitors LLM / reasoning model failure rates:
- **`CLOSED` (Normal Operation):** Calls route to the primary model or local Ollama daemon.
- **`OPEN` (Tripped / Failure State):** If consecutive failures or timeouts exceed the threshold, calls fail fast into deterministic rule-based planning.
- **`HALF_OPEN` (Trial Recovery):** After the recovery timeout (default 60s), a single probe request is permitted to determine if service health is restored.

### 2.3 Consequential Risk Gating
Any action matching destructive patterns (e.g., `del`, `format`, `rmdir`, `drop table`, or sensitive credential operations) is classified as `RiskLevel.HIGH` or `RiskLevel.CONSEQUENTIAL`. Autonomous execution is strictly inhibited until explicit operator confirmation is received via the frontend console.

---

## 3. Daily Operational Workflow & Lifecycle

### 3.1 Normal System Startup
To launch the verified COMPASS environment cleanly:
```powershell
# 1. Start the backend service
py -3.11 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# 2. In a separate terminal, launch the frontend console
cd frontend
npm run dev
```

### 3.2 Controlled Graceful Shutdown
```powershell
# Run the automated cleanup and termination script
python scripts/stop_compass.py
```
This terminates active automation workers, releases Win32 hooks, and ensures no orphan processes or locks remain.

### 3.3 Emergency Abort Procedure
In the event of unexpected application behavior:
1. **Frontend GUI:** Click the red **EMERGENCY STOP** button in the header.
2. **REST API:** Issue an immediate HTTP request:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/tasks/{task_id}/stop
   ```
3. **Execution Latency:** Execution is guaranteed to halt within **55.81 ms** (SLA < 200ms).

---

## 4. Telemetry, Health Checks & Log Monitoring

- **Health Endpoint:** `GET http://127.0.0.1:8000/health` (Returns database status, active task count, memory RSS).
- **Diagnostics View:** Integrated into the React frontend (`src/components/DiagnosticsView.jsx`), exposing real-time SSE task streaming, circuit breaker states, and system memory consumption.
- **Log Files:** Stored in `storage/logs/compass.log` with automatic credential redaction (tokens, passwords, API keys are sanitized before writing to disk).
