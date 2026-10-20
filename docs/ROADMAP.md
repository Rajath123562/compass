# COMPASS — Architecture Roadmap (14 Core Phases)

COMPASS is structured into **14 sequential engineering phases**. There is no Phase 15 or Phase 24; continuous assurance and post-release hardening operate cross-cutting across this 14-phase core.

---

## The 14 Engineering Phases

* **Phase 1: Foundation & Perception Core** — UI Automation (UIA) tree traversal, Win32 window discovery, and OpenCV visual diffing.
* **Phase 2: Task Modeling & State Machine** — Explicit task lifecycles, states (`STARTING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `FAILED`, `STOPPED`, `CANCELLED`, `BLOCKED`), and database persistence.
* **Phase 3: AI Planner & Model Routing** — OmniRoute gateway, free/local model discovery, and prompt synthesis.
* **Phase 4: Action Dispatch & Basic Execution** — Win32 mouse/keyboard synthesis, focus management, and coordinate safety bounds.
* **Phase 5: Decision Engine & Recovery** — Structured classification of failures, retry policies, and automated replanning.
* **Phase 6: Multi-Step Decomposed Planning** — DAG dependency resolution, plan decomposition, and `PlanValidator` structural enforcement.
* **Phase 7: Multimodal Perception & Verification** — Visual region verification, OCR integration (WinRT/Tesseract), and outside-in observation.
* **Phase 8: Autonomous Workflows & Browser Integration** — Multi-node workflow graphs, Playwright browser accessibility trees, and concurrency locks.
* **Phase 9: Interactive Guidance & Standard Protocols** — User chat guidance, step undo, and Model Context Protocol (MCP) server integration.
* **Phase 10: Robustness, Fault Tolerance & Recovery** — Circuit breaker patterns, crash recovery, and offline fallback.
* **Phase 11: Defect Remediation & Verification Hardening** — Elimination of false positives, stale state detection, and strict postcondition checking.
* **Phase 12: End-to-End User Experience & UI Overlay** — Transparent desktop overlay, real-time bounding box highlighting, and frontend Vite console.
* **Phase 13: Adversarial Robustness & Security Hardening** — Threat modeling, origin trust boundaries, input fuzzing, and secret hygiene.
* **Phase 14: Release Certification & Continuous Assurance** — Automated master runner, 8 mandatory release gates, and permanent regression verification.
