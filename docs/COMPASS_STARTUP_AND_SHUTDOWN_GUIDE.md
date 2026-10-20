# COMPASS Startup, Shutdown & Operational Lifecycle Guide

**Product:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Version:** 2.0.0  
**Target OS:** Microsoft Windows 11 64-bit  
**Document Location:** `docs/COMPASS_STARTUP_AND_SHUTDOWN_GUIDE.md`  

---

## 1. Architecture Overview & Components

COMPASS operates as a coordinated multi-component system designed for Windows desktop guidance:

1. **FastAPI Backend Service (`backend.app.main:app`)**:
   - Host & Port: `127.0.0.1:8000`
   - Role: Core REST API, cognitive agent loop, SQLite persistence (`storage/compass.db`), UI Automation dispatcher, WinRT OCR perception pipeline, and safety risk classifier.
   - Health Readiness Probe: `GET http://127.0.0.1:8000/api/health`
2. **React + Vite Frontend Console (`frontend/`)**:
   - Host & Port: `127.0.0.1:5173`
   - Role: Operator console, task submission, real-time SSE execution telemetry, audit log browser, and system metrics dashboard.
3. **PySide6 Desktop Overlay HUD (`overlay/launcher.py`)**:
   - Optional component: Transparent, click-through desktop overlay displaying guidance bounding boxes and visual indicators directly over target Windows applications.
4. **Local AI Reasoning Engine (Optional / Automatic Fallback)**:
   - Local Ollama server at `http://127.0.0.1:11434` or built-in deterministic heuristic rule planner.

---

## 2. Supported Startup Procedures

COMPASS provides three primary startup mechanisms depending on user workflow.

### Method A: One-Click Windows Batch Launcher (Recommended for Everyday Use)
Double-click or run from PowerShell/cmd:
```cmd
START_COMPASS.bat
```
*What this does:*
- Invokes the supervised lifecycle manager via Python 3.11.
- Verifies Python and Node.js environment prerequisites.
- Starts the FastAPI backend daemon on `127.0.0.1:8000`.
- Starts the React/Vite dev server on `127.0.0.1:5173`.
- Polls `/api/health` until HTTP 200 OK is received.
- Records child PIDs in `.compass_pids.json`.
- Launches your default web browser directly to `http://127.0.0.1:5173`.

### Method B: Unified Python Supervisor (Recommended for Developers & Scripts)
Execute using Python 3.11:
```powershell
# Standard launch (Backend + Frontend Web Console)
py -3.11 scripts/start_compass.py

# Launch with transparent PySide6 desktop overlay HUD
py -3.11 scripts/start_compass.py --with-overlay

# Launch backend headless service only (API development & testing)
py -3.11 scripts/start_compass.py --backend-only --no-browser
```

### Method C: Windows PowerShell Script
```powershell
powershell -ExecutionPolicy Bypass -File .\START_COMPASS.ps1
```

---

## 3. Active Readiness Verification

To verify that COMPASS is ready for operation, test the endpoints using any standard tool:

### 3.1 Backend Health & Persistence Check
```powershell
py -3.11 -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:8000/api/health'); data = json.loads(res.read()); print(f'Status: {data[\"status\"]}, DB: {data[\"database\"][\"journal_mode\"]}, Latency: {data[\"database\"][\"latency_ms\"]}ms')"
```
*Expected Output:*
```text
Status: healthy, DB: wal, Latency: <50ms
```

### 3.2 Frontend Availability Check
Open a web browser to:
```text
http://127.0.0.1:5173
```
Confirm the COMPASS Header displays the green `System Healthy` badge and the Workspace view is interactive.

### 3.3 Active Window Context Check
```powershell
py -3.11 -c "import urllib.request; res = urllib.request.urlopen('http://127.0.0.1:8000/api/system/context'); print(res.read().decode())"
```
Returns the currently focused Windows application title, HWND, and bounding dimensions.

---

## 4. Supported Shutdown Procedure

Never forcefully terminate the entire machine or kill arbitrary processes. Use the supported non-destructive shutdown tools.

### Method A: One-Click Batch Stopper
Double-click or run from command prompt:
```cmd
STOP_COMPASS.bat
```

### Method B: Python Safe Stopper
```powershell
py -3.11 scripts/stop_compass.py
```
*What the stopper does:*
1. Reads active PIDs from `.compass_pids.json`.
2. Inspects each tracked process to confirm its command line matches confirmed COMPASS markers (`uvicorn`, `backend.app.main`, `vite`, `overlay.launcher`).
3. Sends graceful SIGTERM signal, waiting for clean shutdown.
4. Flushes SQLite WAL buffers to disk to guarantee zero database corruption.
5. Removes `.compass_pids.json`.
6. Checks ports `8000`, `5173`, and `8001`, confirming they are completely released.
7. Emits a clean exit code `0`.

---

## 5. Troubleshooting Startup Conflicts

| Symptom | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| `Port 8000 in use` | A previous backend instance did not terminate cleanly | Run `STOP_COMPASS.bat` or `py -3.11 scripts/stop_compass.py` to auto-release the port. |
| `Port 5173 in use` | Lingering Node dev server | Run `STOP_COMPASS.bat` to terminate orphaned Vite instances. |
| `Backend failed to respond within 20s` | Missing Python dependency or virtual environment mismatch | Run `py -3.11 scripts/validate_env.py` to diagnose package status. |
| `PySide6 overlay not rendering` | Display scaling issue or headless mode | PySide6 is optional; COMPASS operates fully via the browser console without overlay. |
| `Database is locked` | Concurrent write lock contention | SQLite WAL mode is configured by default; ensure no external SQLite viewer locks `storage/compass.db`. |
