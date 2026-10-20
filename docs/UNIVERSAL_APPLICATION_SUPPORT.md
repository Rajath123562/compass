# COMPASS — Universal Application Support

This document specifies how COMPASS adheres to the Universal Application Support design principles, ensuring it operates as a general-purpose AI system across digital interfaces without application-specific hardcoding.

## 1. Core Principle
COMPASS understands the **interface and user's goal**, not the application name. The execution lifecycle (`UNDERSTAND -> PERCEIVE -> IDENTIFY -> PLAN -> VALIDATE -> SAFETY CHECK -> ACT/GUIDE -> VERIFY -> ADAPT`) is strictly application-independent.

## 2. Universal Perception
COMPASS constructs a normalized internal representation of the digital environment using:
- Windows UI Automation (`uia_inspector.py`)
- Accessibility Trees / Playwright (`browser_adapter.py`)
- Visual OCR (`ocr_engine.py`)
- OpenCV Pixel/SSIM analysis (`opencv_processor.py`)

All observations fuse into `ObservationSnapshot` (see `perception/evidence_fusion.py`). This abstracted interface ensures the planner logic treats a 3D viewport in Blender the same way it treats a DOM element in a browser.

## 3. Capability Hierarchy
COMPASS dynamically falls back through capabilities to guarantee reliability:
1. **Semantic Application Operation:** (e.g. Chrome CDP / Extension / specific API if available)
2. **Accessibility/UIA:** Standard `InvokePattern` / `ValuePattern` in UIA
3. **DOM/Browser Semantic:** Playwright selectors
4. **Structured UI interaction:** Fallback SendInput at bounding box centers
5. **Keyboard/Mouse Fallback:** Raw Win32 inputs

## 4. Mixed Mode Operation (Guide & Assist)
Users can dynamically switch interaction modes during a session:
- **Guide Mode:** Uses `overlay_window.py` to highlight elements and draw text instructions without modifying system state.
- **Assist Mode:** The agent performs validated actions (Click/Type) securely.
- **Mixed Mode:** The agent provides verbal/visual guidance, and steps in to assist when explicitly asked ("Do this for me").

## 5. Application-Independent Verification & Recovery
- **Verification:** Uses OpenCV SSIM (`compare_regions`) and UIA tree diffs to verify structural changes.
- **Recovery:** If an action fails or the screen diverges from the expected state, COMPASS invokes its `failure_recovery` state loop.

## 6. Universality Evaluation Suite
We provide an automated suite (`scripts/universality_evaluation.py`) that explicitly verifies COMPASS's ability to plan, act, and verify across entirely distinct applications (e.g., standard Win32 Notepad, Chromium browsers, Calculator) without modification to the core agent logic.
