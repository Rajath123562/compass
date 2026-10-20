# COMPASS Known Limitations & Operational Boundaries

**Product:** COMPASS (AI-Based System for Guiding Users Through Complex Digital Interfaces)  
**Version:** 2.0.0  
**Status:** Documented Quality Boundaries & Non-Blocking Constraints  
**Document Location:** `docs/COMPASS_KNOWN_LIMITATIONS.md`  

---

## 1. Transparency & Disclosure Mandate

COMPASS v2.0.0 is an evidence-backed, verified system designed for desktop guidance and automation. In strict accordance with engineering integrity principles, all known architectural constraints, OS-level limitations, and operational boundaries are fully disclosed below.

---

## 2. Operating System & Security Boundaries

### 2.1 Windows User Account Control (UAC) Secure Desktop Prompts
- **Boundary**: When a Windows application requests administrative elevation, Windows switches execution to the isolated Winlogon "Secure Desktop" (`Desktop: Winlogon`).
- **Limitation**: Standard user-mode processes cannot inspect elements or dispatch mouse/keyboard inputs into the Secure Desktop. Overriding this requires a digitally code-signed binary from a trusted authority installed in `Program Files` with `uiAccess=true`.
- **Operational Guidance**: Do not initiate tasks requiring administrative elevation without manual operator intervention to approve the UAC dialog.

### 2.2 Exclusive Fullscreen 3D Applications
- **Boundary**: Video games and graphics software running in exclusive fullscreen mode bypass the Windows Desktop Window Manager (DWM).
- **Limitation**: The UI Automation COM tree is inaccessible, and screen grabs may return black frames.
- **Operational Guidance**: Target applications must run in Windowed or Borderless Windowed mode.

### 2.3 Display DPI Scaling Across Multi-Monitor Setups
- **Boundary**: Testing and coordinate calibration were performed on a primary display at 125% DPI scaling (1536x864).
- **Limitation**: If a target application window is dragged between multiple monitors with different DPI scaling settings (e.g. 100% on monitor 1 and 175% on monitor 2), coordinate translation can experience brief offsets until window bounds are re-polled.
- **Operational Guidance**: For automated workflows, keep target applications docked on the primary Windows display.

---

## 3. Cognitive & Automation Boundaries

### 3.1 Non-Accessible Custom Canvas Applications
- **Boundary**: Certain legacy software or proprietary graphics suites do not implement standard Microsoft UI Automation (UIA) accessibility patterns.
- **Limitation**: In such applications, UIA tree traversal cannot identify individual buttons or text inputs.
- **Operational Guidance**: COMPASS automatically falls back to native WinRT OCR and visual template matching. However, OCR resolution is dependent on font legibility and visual contrast.

### 3.2 Offline Cloud LLM Providers
- **Boundary**: The offline regression suite and local production freeze intentionally skip tests requiring external OpenAI or Anthropic API endpoints.
- **Limitation**: When external cloud API keys are not supplied in `.env`, COMPASS operates using its built-in rule-based engine or local Ollama server.
- **Operational Guidance**: For users desiring cloud model reasoning, valid API keys must be explicitly configured in `.env`.

### 3.3 Clipboard History Sensitivity
- **Boundary**: When typing or pasting data into desktop forms, text copied to the clipboard enters the Windows clipboard buffer.
- **Limitation**: Windows Clipboard History (`Win + V`) may retain pasted text until cleared or until the user logs off.
- **Operational Guidance**: Avoid pasting sensitive passwords into automated input fields; type credentials manually when required.

---

## 4. Operational Safety Constraints

- **No Unattended Autonomous Operation**: COMPASS is an operator guidance assistant. It is not approved for unsupervised autonomous execution of financial transactions, destructive file deletions, or system administrative reconfigurations.
- **Consequential Action Gating**: High-risk actions (`delete_file`, `format_disk`, `execute_destructive_command`) are permanently intercepted into `SAFETY_BLOCKED` status and will never execute without explicit human approval.
