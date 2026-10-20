# COMPASS Operations Guide

**Project:** COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces  
**Document Purpose:** Daily Operational Reference, Startup/Shutdown Procedures, Configuration, Diagnostics, and Troubleshooting  
**Date:** 2026-10-18  

---

## 1. Quick Start

### 1.1 Prerequisites
1. **Windows 11** (64-bit).
2. **Python 3.11** (installed and added to `PATH`).
3. **Node.js** (v18+ recommended) and `npm`.
4. **Ollama Desktop** running locally:
   - Verify Ollama is running: open browser at `http://127.0.0.1:11434/` (should display "Ollama is running").
   - Recommended local model: `ollama run qwen3.5:4b`.

### 1.2 One-Click Launch
Double-click `START_COMPASS.bat` in the project root:
- Runs pre-flight port checks (ports 8000 and 5173).
- Initializes the FastAPI backend on `http://127.0.0.1:8000`.
- Starts the Vite frontend on `http://localhost:5173`.
- Automatically opens your default web browser to `http://localhost:5173`.

### 1.3 One-Click Shutdown
Double-click `STOP_COMPASS.bat` in the project root:
- Gracefully terminates running Uvicorn and Vite processes.
- Cleans up child processes without disturbing unrelated background software.

---

## 2. Configuration Reference

The application configuration is managed via `.env` in the root folder, validated by `backend/app/config.py`:

```ini
# Core Server Configuration
COMPASS_HOST=127.0.0.1
COMPASS_PORT=8000
FRONTEND_PORT=5173

# Local AI Model Configuration (Free-Only Enforcement)
COMPASS_FREE_ONLY=True
OLLAMA_BASE_URL=http://127.0.0.1:11434
COMPASS_DEFAULT_MODEL=local/ollama/qwen3.5:4b

# Safety & Execution Boundaries
COMPASS_MAX_RETRIES=3
COMPASS_LLM_TIMEOUT=60.0
COMPASS_ACTION_TIMEOUT=5.0
COMPASS_PANIC_KEY=esc

# Database
COMPASS_DB_PATH=backend/app/compass.db
```

---

## 3. Real-Time Diagnostics & Health Monitoring

### 3.1 Health Endpoint (`GET /api/health`)
Provides the authoritative health status of all subsystems:
```json
{
  "status": "healthy",
  "app": "COMPASS",
  "version": "1.0.0",
  "uptime_seconds": 1245.8,
  "subsystems": {
    "database": {"status": "healthy", "detail": "SQLite WAL connected"},
    "ai_provider": {"status": "healthy", "detail": "Local Ollama Active"},
    "perception": {"status": "healthy", "detail": "Windows UIA Initialized"},
    "automation": {"status": "healthy", "detail": "Win32 Dispatcher Ready"}
  }
}
```

### 3.2 System Telemetry (`GET /api/system/info`)
Returns real-time hardware telemetry:
- CPU utilization percentage.
- Memory used by process (MB) and physical RAM available.
- Active foreground window title and executable path.

### 3.3 Interactive Telemetry Modal
In the frontend dashboard, click the telemetry pill in the footer (`System Ready · 20ms loopback · 69 MB Process RAM`) to open the `SystemTelemetryModal` showing live diagnostics.

---

## 4. Operational Troubleshooting

| Symptom | Probable Cause | Corrective Action |
|---|---|---|
| **"Backend unavailable" banner in UI** | FastAPI backend is not running or crashed | Run `START_COMPASS.bat` or inspect `python backend/app/main.py` in terminal. |
| **"AI Unavailable" when starting a task** | Local Ollama is offline or model not pulled | 1. Ensure Ollama Desktop is running in system tray.<br>2. Run `ollama list` in terminal to confirm `qwen3.5:4b` is present. |
| **Task enters `WAITING_CONFIRMATION`** | High-risk action detected (e.g. file edit, shell command) | Review the action in the UI card and click "Approve Action" or "Reject Action". |
| **Emergency abort needed** | Agent is typing or moving mouse into unwanted target | Press the `Esc` key or click "Emergency Stop" in the UI capsule. |
| **Model list not updating after `ollama pull`** | 30s TTL model cache is active | Click "Refresh Models" in the Settings view or wait 30 seconds for automatic cache expiry. |

---

## 5. Maintenance & Log Rotation
- **SQLite Database:** Located at `backend/app/compass.db`. Backed by WAL journaling (`compass.db-wal`). Run `VACUUM` periodically if historical task entries exceed 10,000 records.
- **Log Files:** Standard application logs are output to stdout and captured in `artifacts/logs/`. Logs are sanitized to strip passwords and API keys.
