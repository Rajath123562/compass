# COMPASS Startup and Recovery Guide

**Project:** COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces  
**Standard:** Phase 13 Reliable Startup & Operational Maintenance Procedure  
**Platform:** Windows 11 Home / Pro (64-bit)  
**Date:** October 17, 2026  

---

## 1. System Requirements & Prerequisites

Before launching COMPASS, verify that the following dependencies are installed on the Windows machine:

1. **Python:** 3.11.x (Installed and available on PATH or in `.venv`)
2. **Node.js:** 18.x or higher (Tested with Node.js 24.18.0 and npm 11.16.0)
3. **Local AI Engine (Ollama):** Installed and running on `http://127.0.0.1:11434`
   - Required Model: `qwen3.5:4b` (Run `ollama pull qwen3.5:4b` to download if not present)
4. **Network Ports Required:**
   - `8000`: FastAPI Backend
   - `5173`: React / Vite Web Interface
   - `11434`: Local Ollama API

---

## 2. Standard Startup Procedure

### Method A: One-Click Windows Batch Launcher (Recommended)

1. Open **Windows PowerShell** or **Command Prompt** in the project directory:
   ```powershell
   cd "C:\Users\RAJATH U\Downloads\personal assitant"
   ```
2. Run the startup batch script:
   ```powershell
   .\START_COMPASS.bat
   ```
   *(Note: In PowerShell, always include `.\` before the script name).*

**What `START_COMPASS.bat` does automatically:**
- Scans and detects the Python interpreter (checks `.venv`, WindowsApps, or system PATH).
- Cleans up any orphaned processes on ports 8000 or 5173 using `scripts/stop_compass.py`.
- Checks if Ollama is running on port 11434; if offline, starts `ollama serve` in the background.
- Launches the unified Python supervisor `scripts/start_compass.py --open-browser --with-overlay`.
- Automatically opens your default web browser to `http://127.0.0.1:5173`.

---

### Method B: Direct Python Supervisor Launch

If you prefer launching directly via Python:
```powershell
python scripts/start_compass.py --open-browser --with-overlay
```

**Available CLI Flags:**
- `--open-browser`: Automatically opens `http://127.0.0.1:5173` upon successful startup.
- `--with-overlay`: Starts the PySide6 transparent desktop HUD overlay.
- `--no-browser`: Suppresses browser launch (useful for headless testing).
- `--duration <seconds>`: Runs the services for a specified number of seconds and then shuts down gracefully (useful for automated health checks).

---

## 3. How to Verify Services are Running

After startup, confirm the system health:

1. **Backend Health Check:**
   Open a browser or PowerShell and query:
   ```powershell
   curl http://127.0.0.1:8000/api/health
   ```
   **Expected Response:**
   ```json
   {"status":"healthy","version":"1.0.0","provider":"omniroute","model":"qwen3.5:4b"}
   ```

2. **Frontend Dashboard:**
   Visit `http://127.0.0.1:5173` in any modern web browser. You should see the COMPASS Guidance Dashboard with live perception status and goal input.

3. **Desktop HUD Overlay (Optional):**
   A transparent HUD window will dock at the top of your screen, showing real-time agent thoughts and actions.

---

## 4. How to Stop COMPASS Safely

To ensure no child processes or port locks are left behind:

### Normal Shutdown
- Press `Ctrl + C` in the console window where the supervisor is running. The supervisor gracefully sends SIGTERM to the backend, frontend, and overlay.

### Dedicated Clean-Stop Utility
If a console was closed abruptly or a port remains bound, execute:
```powershell
python scripts/stop_compass.py
```
This utility:
- Queries `netstat` for processes listening on ports 8000 and 5173.
- Gracefully terminates them via `os.kill` / `taskkill`.
- Releases all network bindings within 2 seconds.

---

## 5. Troubleshooting & Common Recovery Procedures

### Issue 1: "Address already in use" (Port 8000 or 5173)
- **Symptom:** Backend or frontend fails to start with `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`.
- **Fix:** Run `python scripts/stop_compass.py`. It immediately finds and terminates the lingering process.

### Issue 2: "Ollama connection refused on 127.0.0.1:11434"
- **Symptom:** Agent logs show `ProviderUnavailableError` or timeout connecting to local model.
- **Fix:**
  1. Open a new terminal and run:
     ```powershell
     ollama serve
     ```
  2. Verify the model is pulled:
     ```powershell
     ollama list
     ```
  3. If `qwen3.5:4b` is not listed, run `ollama pull qwen3.5:4b`.

### Issue 3: Missing Node modules or frontend assets
- **Symptom:** Vite fails with `command not found: vite`.
- **Fix:** Run `npm --prefix frontend install` to restore dependencies.

### Issue 4: Python dependencies out of sync
- **Symptom:** `ModuleNotFoundError: No module named 'fastapi'` or `playwright`.
- **Fix:** Run:
  ```powershell
  pip install -r requirements.txt
  playwright install chromium
  ```

---

## 6. How to Run the Regression Test Suite

To verify code integrity after making changes:

```powershell
# 1. Run Python unit and integration tests
pytest backend/ perception/ automation/ providers/ assurance/ planner/

# 2. Run Playwright browser automation tests
pytest automation/tests/test_browser_adapter.py

# 3. Run Computer Vision tests
pytest perception/tests/test_opencv_processor.py

# 4. Run Frontend unit tests
npm --prefix frontend test

# 5. Run Security & Secrets audit
python scripts/audit_security_secrets.py

# 6. Run Live Acceptance audit
python scripts/audit_phase4_acceptance.py
```
