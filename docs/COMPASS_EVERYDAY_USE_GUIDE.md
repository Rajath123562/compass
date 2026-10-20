# COMPASS Everyday Use & Operator Guide

**Product:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Version:** 2.0.0  
**Target Audience:** Operators, Knowledge Workers, and System Administrators  
**Document Location:** `docs/COMPASS_EVERYDAY_USE_GUIDE.md`  

---

## 1. Quick-Start Everyday Routine

### 1.1 Starting COMPASS
1. Launch COMPASS using `START_COMPASS.bat` from the project folder.
2. The browser automatically navigates to `http://127.0.0.1:5173`.
3. Check the header status indicator: confirm the green **System Healthy** badge is active.

### 1.2 Stopping COMPASS
1. When your session is finished, run `STOP_COMPASS.bat`.
2. All background services and ports (`8000`, `5173`) are released cleanly.

---

## 2. Navigating the Operator Console

The COMPASS console is divided into primary views accessible via the sidebar:

- **Workspace**: The central interface for submitting tasks, selecting target applications, viewing real-time execution steps, and inspecting final outcomes.
- **Task History**: Search and review previously completed, stopped, or failed tasks, including step-by-step audit logs.
- **Audit Logs**: Tamper-evident operational event stream detailing every perception, plan, and dispatch event.
- **System Status**: Telemetry monitor displaying process RAM/CPU usage, active window context, database WAL size, and registered tools.

---

## 3. Submitting Tasks & Lifecycle States

### 3.1 Submitting a Task
1. In the **Workspace** view, enter a clear, specific natural language goal into the input box:
   - *Example*: `"Calculate total sum of 450 + 820 in Windows Calculator"`
   - *Example*: `"Open Notepad and type release notes header"`
2. Click **Start Task**.

### 3.2 Understanding Task States

| State | Badge Color | Meaning & Operator Action |
| :--- | :--- | :--- |
| `CREATED` | Gray | Task registered and queued in database. |
| `STARTING` | Blue | Cognitive loop initializing for execution. |
| `UNDERSTANDING` | Blue | Parsing goal semantics and required capabilities. |
| `OBSERVING` | Purple | Inspecting active desktop window and OCR text. |
| `PLANNING` | Indigo | Formulating DAG step plan or action sequence. |
| `EXECUTING` | Amber | Dispatching verified mouse/keyboard actions to OS. |
| `COMPLETED` | Green | Task finished successfully; result verified. |
| `SAFETY_BLOCKED` | Red | High-risk action detected; awaiting human approval. |
| `STOPPED` | Orange | Task halted by operator clicking STOP. |
| `FAILED` | Red | Task encountered unrecoverable tool or system error. |

---

## 4. Controlled Everyday-Use Rollout Plan

To ensure maximum safety and reliability, introduce COMPASS into your daily workflow through four progressive stages:

### Stage 1: Basic Low-Risk & Reversible Tasks
Begin exclusively with non-destructive, isolated utilities:
- Calculations in Windows Calculator (`calc.exe`).
- Entering notes in a fresh, untitled Windows Notepad document.
- Querying active window title and context telemetry.
- Enumerate files in a designated temporary test directory.
*Rule:* Confirm visual output manually after each operation.

### Stage 2: Multistep & Compound Tasks
Progress to sequential workflows with topological dependencies:
- Capturing a specific window region, running OCR, and displaying extracted text.
- Formulating a 3-step action plan for application navigation.
*Rule:* Verify intermediate step progress in the Task Card before execution completes.

### Stage 3: Normal Everyday Productivity
Use COMPASS within its verified capability boundaries:
- Assisting with data entry into forms where actions are easily reviewed.
- Guiding operators through multi-screen desktop workflows.
*Rule:* Keep consequential actions (file deletion, network requests) under Human-in-the-Loop review.

### Stage 4: Ongoing Monitored Use & Defect Logging
When unexpected behavior occurs during daily use, document the incident using the structured defect schema:
1. **User Goal Requested**: What instruction was given?
2. **Action Taken by COMPASS**: What steps did COMPASS attempt?
3. **Expected Result**: What should have happened?
4. **Actual Result**: What happened instead?
5. **Target Window & HWND**: Which application was active?
6. **Task ID**: Record the UUID from the Task Card.
7. **Audit Log Snippet**: Export relevant log events from the Audit Log view.

---

## 5. Emergency Stop & Task Cancellation

If COMPASS begins performing an unintended action or targets the wrong window:

1. **Immediate Web STOP Button**: Click the prominent red **STOP** button located directly on the active Task Card in the Web Console.
2. **Keyboard Stop Signal**: If using the PySide6 overlay HUD, press `Esc` to immediately halt execution.
3. **API Emergency Abort**: Run from command line:
   ```powershell
   py -3.11 -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/api/tasks/stop-all', method='POST'))"
   ```
*Response Time:* Active dispatch hooks and mouse movements terminate within 150ms of receiving the stop signal.
