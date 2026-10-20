# COMPASS Supported Capabilities & Verification Matrix

**Product:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Version:** 2.0.0  
**Verification Standard:** ISO/IEC 25010 Empirical System Capability Review  
**Document Location:** `docs/COMPASS_SUPPORTED_CAPABILITIES.md`  

---

## 1. Verified Capability Matrix

The table below delineates the verified capabilities of the COMPASS v2.0.0 release. Capabilities are categorized strictly by their measured empirical status on live Windows host hardware.

| Capability Area | Implemented Status | Verification Status | Supported Environment | Known Limitations | Required Permissions | Safe Operating Conditions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Task Understanding** | Full Implementation | **VERIFIED (PASS)** | Backend API (Python 3.11) | Complex nested negative constraints require clear phrasing | Standard User | Well-formed English natural language goals (>=2 chars) |
| **Cognitive Planning** | Full Implementation | **VERIFIED (PASS)** | Deterministic Rule Engine & Ollama | Plan depth capped at 10 sequential sub-steps | Standard User | Reversible workflows; verified tool catalog items |
| **Workflow DAG Execution** | Full Implementation | **VERIFIED (PASS)** | `workflow_engine.py` | Graph must be acyclic (DAG); cycles blocked at parse time | Standard User | Explicit dependency relationships between nodes |
| **Windows UI Automation** | Full Implementation | **VERIFIED (PASS)** | Windows 11 Desktop (Win32 UIA) | UAC secure desktop prompts and exclusive fullscreen games not accessible | Standard User | Target application visible on primary display (100-150% DPI) |
| **WinRT Native OCR** | Full Implementation | **VERIFIED (PASS)** | Windows 11 Native OCR Engine | High visual noise or low contrast text may degrade accuracy | Standard User | Clear fonts, standard DPI scaling, non-obfuscated UI |
| **Action Dispatch (SendInput)** | Full Implementation | **VERIFIED (PASS)** | Win32 User32 API | Cannot dispatch keystrokes into elevated administrator prompts from user process | Standard User | `StaleGuard` verified foreground focus before each keystroke/click |
| **PySide6 Overlay HUD** | Full Implementation | **VERIFIED (PASS)** | Qt 6.7.2 Click-Through Canvas | Requires graphics driver supporting transparent layered windows | Standard User | Desktop window manager (DWM) composition enabled |
| **Safety Risk Classification** | Full Implementation | **VERIFIED (PASS)** | `RiskClassifier` Rules Engine | Relies on keyword and path heuristics; HITL gate mandatory for high risk | Standard User | All file deletion, DB drops, format commands strictly gated |
| **Task Cancellation (STOP)** | Full Implementation | **VERIFIED (PASS)** | REST API + Cognitive Loop | Dispatches within 150ms; mid-step Win32 SendInput burst completes before halt | Standard User | Web Console STOP button or `POST /api/tasks/{id}/stop` |
| **Browser Interaction** | Adapter Ready | **PARTIALLY VERIFIED** | Playwright Chromium CDP | Headless/browser CDP adapter verified; arbitrary extension interaction out of scope | Standard User | Local web applications on loopback or standard public websites |
| **Local Model Inference** | Full Implementation | **VERIFIED (PASS)** | Local Ollama (`127.0.0.1:11434`) | Requires local Ollama service running if LLM mode selected | Standard User | Rule-based engine active as default fallback |
| **Cloud Model Inference** | Full Implementation | **PARTIALLY VERIFIED (BYPASS)** | OpenAI / Anthropic APIs | Requires active internet and valid paid API keys; bypassed during offline audit | Standard User + API Key | User explicitly opts into cloud mode via `.env` |
| **Persistence & Audit Logging** | Full Implementation | **VERIFIED (PASS)** | SQLite 3.45 WAL Mode | Database file must be on local filesystem (UNC paths not recommended) | Standard User | Standard write permissions in `storage/` and `logs/` |
| **System Resource Telemetry** | Full Implementation | **VERIFIED (PASS)** | Psutil + Win32 Telemetry | Telemetry polled at ~1s intervals | Standard User | Local loopback querying of `/api/system/context` |

---

## 2. Tested Application Allowlist

The following Windows applications have undergone rigorous empirical testing with COMPASS v2.0.0:

1. **Windows Calculator (`calc.exe` / modern UWP CalculatorApp)**:
   - *Status*: **VERIFIED (PASS)**.
   - *Verified Operations*: Numeric button identification via UIA COM tree, operator clicks (`7 * 8 =`), display result extraction (`"56"`).
2. **Windows Notepad (`notepad.exe`)**:
   - *Status*: **VERIFIED (PASS)**.
   - *Verified Operations*: Document edit control focus, virtual typing simulation, WinRT OCR verification, safe discard on close.
3. **Windows Paint (`mspaint.exe`)**:
   - *Status*: **VERIFIED (PASS)**.
   - *Verified Operations*: Canvas bounding box isolation, tool ribbon enumeration, DPI-scaled coordinate alignment.
4. **Windows File Explorer (`explorer.exe`)**:
   - *Status*: **VERIFIED (PASS)**.
   - *Verified Operations*: Shell folder navigation, item enumeration in list view, path address verification.
5. **Local Web Application Console (`http://127.0.0.1:5173`)**:
   - *Status*: **VERIFIED (PASS)**.
   - *Verified Operations*: Task submission, real-time SSE stream consumption, navigation tabs, audit log filtering.

---

## 3. Disclosed Unverified Scope

The following capabilities exist in architectural concept or experimental code but are **NOT** certified for regular everyday use:

- Unattended overnight automation without human supervision.
- Financial transactions, online purchasing, or account authentication.
- Interaction with Windows administrative UAC prompts.
- Interaction with hardware-accelerated exclusive fullscreen 3D games.
